<template>
  <div class="container">
    <div class="top">
      <div>
        <h5>Don't search for very common words, you'll kill the tab.</h5>
        <input-text v-model="search_term" type="text" placeholder="Search" :loading="is_loading"
          @keyup.enter="search()" />
        <Button label="Search" @click="search()" />
      </div>
      <div>
        <ProgressBar class="mt-2" v-if="is_loading" mode="indeterminate" style="height: 6px" />
      </div>
    </div>
    <div class="vodlist ">
      <div class="text-center w-full">
        Vods
      </div>
      <ScrollPanel style="width: 100%; height: 90vh">
        <Listbox :options="results" optionLabel="content" class="w-full" @change="select_vod($event)"
          :emptyMessage="search_completed ? 'No results for that search term.' : 'Search something to get results.'">
          <template #option="slotProps">
            <div class="grid-nogutter align-items-center">
              <div class="col-12">
                {{ slotProps.option.date }} {{ slotProps.option.game }} <br />
              </div>
              <div class="col-12">
                <span class="text-xs">{{ slotProps.option.title }}</span> <br />
              </div>
            </div>
          </template>
        </Listbox>
      </ScrollPanel>
    </div>
    <div class="transcript">
      <div class="text-center w-full">
        Lines
      </div>
      <ScrollPanel style="width: 100%; height: 90vh">
        <Listbox :options="selected_vod_sentences" optionLabel="content" class="w-full" @change="playsegment($event)">
          <template #option="slotProps">
            <div class="flex align-items-center">
              <div style="min-width: 100px;">{{ timeToPrettyString(slotProps.option.start_time) }}</div>
              <!-- <div style="min-width: 100px;">{{ slotProps.option.end_time }}</div> -->
              <div class="ml-2">{{ slotProps.option.content }}</div>
            </div>
          </template>
        </Listbox>

      </ScrollPanel>
    </div>
    <div class="video">
      <div class="text-center w-full">
        Video
      </div>
      <div class="text-center" v-if="player_loading">
        Video is loading, give it a sec.. <br />
        <ProgressSpinner />
      </div>
      <video controls ref="vodplayer" v-show="show_player" style="max-width: 33vw;">
        <source src="" type="video/mp4">
        Your browser does not support the video tag.
      </video>
    </div>

  </div>
</template>
  
<script setup>
import { ref, onMounted } from 'vue'
import { createDbWorker } from "sql.js-httpvfs";

const search_term = ref('')
const is_loading = ref(false)
const vodplayer = ref()
const show_player = ref(false)
const player_loading = ref(false)

const results = ref()
const search_completed = ref(false)
const selected_vod_sentences = ref()


const publicPath =
  process.env.NODE_ENV === "production" ? "/joe-videosearch/" : "/static/";

const workerUrl = new URL(
  `${publicPath}sqlite.worker.js`,
  import.meta.url
);
const wasmUrl = new URL(
  `${publicPath}sql-wasm.wasm`,
  import.meta.url
);

import dbdata from '/static/data.json'
const dbworker = ref()

onMounted(async () => {
  dbworker.value = await createDbWorker(
    [
      {
        from: "jsonconfig",
        configUrl: dbdata.dir_name + "/config.json"
      }
    ],
    workerUrl.toString(),
    wasmUrl.toString()
  );
})

function timeToSeconds(timeString) {
  // Split the time string into its components
  const [hours, minutes, seconds, milliseconds] = timeString.split(/[:,]/);

  // Convert the components to numbers
  const hoursInSeconds = parseInt(hours, 10) * 3600;
  const minutesInSeconds = parseInt(minutes, 10) * 60;
  const secondsInSeconds = parseInt(seconds, 10);
  const millisecondsInSeconds = parseFloat("0." + milliseconds);

  // Calculate the total time in seconds
  const totalTimeInSeconds =
    hoursInSeconds + minutesInSeconds + secondsInSeconds + millisecondsInSeconds;

  return totalTimeInSeconds;
}

function timeToPrettyString(timeString) {
  const [hours, minutes, seconds, milliseconds] = timeString.split(/[:,]/);

  if (hours == 0) {
    return `${minutes}m${seconds}s`;
  }
  return `${hours}h${minutes}m${seconds}s`;

}

async function select_vod(event) {
  selected_vod_sentences.value = event.value.sentences;
}

async function playsegment(event) {
  const video = vodplayer.value
  video.src = event.value.video_url;
  video.load();
  show_player.value = false;
  player_loading.value = true;

  video.onloadeddata = () => {
    video.currentTime = timeToSeconds(event.value.start_time);
    video.play();
    show_player.value = true;
    player_loading.value = false;
  };
}

async function search() {
  is_loading.value = true;
  results.value = [];

  let query = `
  select vod_id, vods.title, video_url, game, date, speaker, start_time, end_time, content
  from transcripts
  left join vods on transcripts.vod = vods.vod_id
  where content like '%${search_term.value}%'
  order by date
`;

  let _ret = await dbworker.value.db.query(query);
  let _sentences = {};
  let _results = [];

  for (let result of _ret) {
    const vod_id = result.vod_id;

    let title = result.title;
    if (!title) {
      title = result.video_url.split("/").pop().split(".")[0].replace(/_/g, " ");
      title = decodeURIComponent(title)
      title = title.split(" - ").slice(0, -1).join(" - ");
    }


    if (!_sentences[vod_id]) {
      _sentences[vod_id] = _results.length;
      _results.push({
        vod_id: vod_id,
        title: title,
        game: result.game,
        date: result.date,
        sentences: [
          {
            speaker: result.speaker,
            start_time: result.start_time,
            content: result.content,
            video_url: result.video_url,
          },
        ],
      });
    } else {
      _results[_sentences[vod_id]].sentences.push({
        speaker: result.speaker,
        start_time: result.start_time,
        content: result.content,
        video_url: result.video_url,
      });
    }
  }

  results.value = _results;
  is_loading.value = false;
  search_completed.value = true;
}

</script>

<style>
video {
  object-fit: fill;
  max-width: 60vw;
}

.container {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  grid-template-rows: auto 0.9fr;
  gap: 0px 0px;
  grid-template-areas:
    "top top top"
    "vodlist transcript video";
}

.top {
  justify-self: center;
  grid-area: top;
}

.vodlist {
  align-self: start;
  grid-area: vodlist;
}

.video {
  align-self: start;
  grid-area: video;
}

.transcript {
  align-self: start;
  grid-area: transcript;
}
</style>