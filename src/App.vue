<template>
  <div class="container">
    <div class="top">
      <div>
        <h5>Don't search for very common words, you'll kill the tab.</h5>
        <input-text v-model="search_term" type="text" placeholder="Search" :loading="is_loading" @keyup.enter="search()" />
        <Button label="Search" @click="search()" />
      </div>
      <div v-if="is_loading">
        <small>Loading is slow the first time as it's downloading the database. <br /></small>
        <ProgressBar class="mt-2" mode="indeterminate" style="height: 6px" />
      </div>
    </div>
    <div class="vodlist ">
      <div class="text-center w-full">
        Vods
      </div>
      <ScrollPanel style="width: 100%; height: 90vh">
        <Listbox :options="results" optionLabel="content" class="w-full" @change="select_vod($event)" :emptyMessage="search_completed ? 'No results for that search term.' : 'Search something to get results.'">
          <template #option="slotProps">
            <div class="grid-nogutter align-items-center flex">

              <div class="col-2">
                <span class="text-xs">{{ slotProps.option.date }}</span>
              </div>
              <div class="col-10">
                {{ slotProps.option.title }}
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
      <div v-if="show_videos" class="video" style="padding-bottom:56.25%;min-height: 300px;">
        <iframe width="100%" height="400px" ref="pt_player" :src="video_url_peertube" allow="autoplay; encrypted-media" allowfullscreen>
        </iframe>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { createDbWorker } from "sql.js-httpvfs";

const search_term = ref('')
const is_loading = ref(false)


const show_videos = ref(false)


const results = ref()
const search_completed = ref(false)
const selected_vod_sentences = ref()
const video_url_peertube = ref('')

const pt_player = ref(null);

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
  show_videos.value = false;
}


const sendVideoMessage = (action) => {
  console.log('Sending message:', action);
  pt_player.value.contentWindow.postMessage(
    JSON.stringify({
      command: action  // Try different message formats
    }),
    '*'
  );
};

// Add message listener to debug
window.addEventListener('message', (event) => {
  console.log('Received message:', event.data);
});

async function playsegment(event) {
  if (!event.value.video_url_peertube) {
    show_videos.value = false;
    return;

  }
  video_url_peertube.value = event.value.video_url_peertube + "?autoplay=1&start=" + timeToSeconds(event.value.start_time);
  show_videos.value = true;

}

async function search() {
  is_loading.value = true;
  results.value = [];

  let query = `
  select vod_id, vods.title, vods.video_url_peertube, vods.date, speaker, start_time, end_time, content
  from transcripts
  left join vods on transcripts.vod = vods.vod_id
  where content like '%${search_term.value}%'
  order by vods.date desc, vods.vod_id desc, start_time, end_time
`;

  let _ret = await dbworker.value.db.query(query);


  let _sentences = {};
  let _results = [];

  for (let result of _ret) {
    const vod_id = result.vod_id;

    let title = result.title;


    if (_sentences[vod_id] === undefined || _sentences[vod_id] === null) {
      _sentences[vod_id] = _results.length;
      _results.push({
        vod_id: vod_id,
        title: title,
        date: result.date,
        sentences: [],
      });
    }
    _results[_sentences[vod_id]].sentences.push({
      speaker: result.speaker,
      start_time: result.start_time,
      content: result.content,
      video_url_peertube: result.video_url_peertube ? result.video_url_peertube.replace('/watch/', '/embed/') : ''
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
