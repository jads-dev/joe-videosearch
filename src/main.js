import { createApp } from 'vue'

// prime stuff
import PrimeVue from 'primevue/config';
import InputText from 'primevue/inputtext';
import Button from 'primevue/button';
import Accordion from 'primevue/accordion';
import AccordionTab from 'primevue/accordiontab';
// import DataView from 'primevue/dataview';
// import DataTable from 'primevue/datatable';
// import Column from 'primevue/column';
import Listbox from 'primevue/listbox';
import ScrollPanel from 'primevue/scrollpanel';
import ProgressBar from 'primevue/progressbar';
import ProgressSpinner from 'primevue/progressspinner';
import TabView from 'primevue/tabview';
import TabPanel from 'primevue/tabpanel';

import 'primevue/resources/themes/viva-dark/theme.css'
import 'primeflex/primeflex.css'


import App from './App.vue'




const app = createApp(App);
app.use(PrimeVue);
app.component('InputText', InputText);
app.component('Button', Button);
app.component('Accordion', Accordion);
app.component('AccordionTab', AccordionTab);
app.component('Listbox', Listbox);
app.component('ScrollPanel', ScrollPanel);
app.component('ProgressBar', ProgressBar);
app.component('ProgressSpinner', ProgressSpinner);
app.component('TabView', TabView);
app.component('TabPanel', TabPanel);
// app.component('DataView', DataView);
// app.component('DataTable', DataTable);
// app.component('Column', Column);
app.mount('#app');