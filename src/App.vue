<template>
  <div class="container">
    <div class="top">
      <div>
        <h5>Don't search for very common words, you'll kill the tab.</h5>
        <input-text v-model="search_term" type="text" placeholder="Search" :loading="is_loading"
          @keyup.enter="search()" />
        <Button label="Search" @click="search()" />
      </div>
      <div v-if="is_loading">
        <small>Loading is slow the first time as it's downloading the database. <br /></small>
        <ProgressBar class="mt-2"  mode="indeterminate" style="height: 6px" />
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
    <div class="text-center w-full">
      Video
      <TabView v-model:activeIndex="active_tab" @tab-change="on_tab_change($event)" :lazy="true" v-if="show_videos">
        <TabPanel header="YouTube" :disabled="!show_yt" class="video" style="padding-bottom:56.25%;min-height: 300px;">
          <p class="my-0" style="font-size: 12px;">
            Some youtube videos are not matched properly, report to nodja if the timestamp/video looks incorrect. Internet Archive version should always be correct.
          </p>

          <iframe width="100%" height="400px" ref="yt_player" :src="video_url_youtube">
          </iframe>
        </TabPanel>
        <TabPanel header="Internet Archive" class="video">
          <div class="text-center" v-show="player_loading">
            Internet Archive is slow, give it a sec.. <br />
            Video is loading. <br />
            <ProgressSpinner />
          </div>
          <video controls ref="vodplayer" style="max-width: 33vw;" v-show="!player_loading">
            <source src="" type="video/mp4">
            Your browser does not support the video tag.
          </video>
        </TabPanel>
      </TabView>
    </div>
  </div>
</template>
  
<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { createDbWorker } from "sql.js-httpvfs";

const search_term = ref('')
const is_loading = ref(false)
const vodplayer = ref()

const show_videos = ref(false)
const show_yt = ref(false)
const video_url_youtube = ref('')
const video_url_ia = ref('')
const video_ts_ia = ref(0)
const player_loading = ref(false)
const active_tab = ref(0);

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

  return parseInt(totalTimeInSeconds);
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
  show_yt.value = false;


  if (event.value.video_url_youtube) {
    show_yt.value = true;
    active_tab.value = 0;
    video_url_youtube.value = "https://www.youtube-nocookie.com/embed/" + event.value.video_url_youtube + "?autoplay=1&start=" + timeToSeconds(event.value.start_time);
  }
  else
    active_tab.value = 1;

  video_url_ia.value = event.value.video_url;
  video_ts_ia.value = timeToSeconds(event.value.start_time);
  show_videos.value = true;
}

async function on_tab_change(event) {
  if (event.index == 1) {
    nextTick(() => {
      const video = vodplayer.value
      video.src = video_url_ia.value;
      video.load();
      player_loading.value = true;
      video.onloadeddata = () => {
        video.currentTime = video_ts_ia.value;
        video.play();
        player_loading.value = false;
      };
    })

  }
}

async function search() {
  is_loading.value = true;
  results.value = [];

  let query = `
  select vod_id, vods.title, video_url, video_url_youtube, game, date, speaker, start_time, end_time, content
  from transcripts
  left join vods on transcripts.vod = vods.vod_id
  where content like '%${search_term.value}%'
  order by vods.date, vods.vod_id, start_time, end_time
`;

  let _ret = await dbworker.value.db.query(query);

  console.log(_ret)
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

    console.log(_sentences)

    const deepCopyResults = JSON.parse(JSON.stringify(_results));
    console.log(deepCopyResults);
    if (_sentences[vod_id] === undefined || _sentences[vod_id] === null) {
      _sentences[vod_id] = _results.length;
      _results.push({
        vod_id: vod_id,
        title: title,
        game: result.game,
        date: result.date,
        sentences: [],
      });
    }
    _results[_sentences[vod_id]].sentences.push({
      speaker: result.speaker,
      start_time: result.start_time,
      content: result.content,
      video_url: result.video_url,
      video_url_youtube: result.video_url_youtube,
    });


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