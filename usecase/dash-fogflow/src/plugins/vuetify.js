import Vue from 'vue';
import HighchartsVue from 'highcharts-vue'
import Vuetify, {
  VCard,
  VRating,
  VToolbar,
} from 'vuetify/lib';
import { Ripple } from 'vuetify/lib/directives'
import { chart } from 'highcharts';


Vue.use(Vuetify, HighchartsVue, {
  components: {
    VCard,
    VRating,
    VToolbar,
  },
  directives: {
    Ripple,
  },
})

const opts = {}

export default new Vuetify(opts)
