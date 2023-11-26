<template>
  <div class="container">
    <div class="top">
      <h5>Don't search for very common words, you'll kill the tab.</h5>
      <input-text v-model="search_term" type="text" placeholder="Search" :loading="is_loading" @keyup.enter="search()" />
      <Button label="Search" @click="search()" />
    </div>
    <div class="video">
      <video controls ref="vodplayer" v-show="show_player">
        <source src="" type="video/mp4">
        Your browser does not support the video tag.
      </video>
    </div>
    <div class="transcript">
      <ScrollPanel style="width: 100%; height: 90vh">
        <Accordion :multiple="true" :activeIndex="[...Array(results.length).keys()]" v-if="results">
          <AccordionTab v-for="result in results">
            <template #header>
              {{ result.date }} {{ result.game }} <br />
              {{ result.title }}
            </template>
            <div>
              <Listbox :options="result.sentences" optionLabel="content" class="w-full" listStyle="max-height:250px"
                @change="playsegment($event)">
                <template #option="slotProps">
                  <div class="flex align-items-center">
                    <div style="min-width: 100px;">{{ slotProps.option.speaker }}</div>
                    <div>{{ slotProps.option.content }}</div>
                  </div>
                </template>
              </Listbox>
            </div>

          </AccordionTab>
        </Accordion>
      </ScrollPanel>

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

const results = ref()


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

async function playsegment(event) {
  const video = vodplayer.value
  video.src = event.value.video_url;
  video.load();
  show_player.value = true;

  video.onloadeddata = () => {

    video.currentTime = timeToSeconds(event.value.start_time);
    video.play();
  };
  console.log(video)
}

async function search() {
  is_loading.value = true;
  results.value = [];

  let query = `
  select vod_id, vods.title, video_url, game, date, speaker, start_time, content
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

    if (!_sentences[vod_id]) {
      _sentences[vod_id] = _results.length;
      _results.push({
        vod_id: vod_id,
        title: result.title,
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
      });
    }
  }

  results.value = _results;
  is_loading.value = false;
}

</script>

<style>
video {
  object-fit: fill;
  max-width: 60vw;
}

.container {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: auto 0.9fr;
  gap: 0px 0px;
  grid-template-areas:
    "top top"
    "video transcript";
}

.top {
  justify-self: center;
  grid-area: top;
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