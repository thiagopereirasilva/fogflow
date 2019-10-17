<template>
  <v-app id="inspire">
    <v-navigation-drawer v-model="drawer" app>
      <v-list dense>
        <v-list-item @click="true">
          <v-list-item-action>
            <v-icon>mdi-home</v-icon>
          </v-list-item-action>
          <v-list-item-content>
            <v-list-item-title>Home</v-list-item-title>
          </v-list-item-content>
        </v-list-item>
        <v-list-item @click="true">
          <v-list-item-action>
            <v-icon>mdi-contact-mail</v-icon>
          </v-list-item-action>
          <v-list-item-content>
            <v-list-item-title>History</v-list-item-title>
          </v-list-item-content>
        </v-list-item>
      </v-list>
    </v-navigation-drawer>

    <v-app-bar app color="indigo" dark>
      <v-app-bar-nav-icon @click.stop="drawer = !drawer"></v-app-bar-nav-icon>
      <v-toolbar-title>Smart Parking2</v-toolbar-title>
    </v-app-bar>

    <v-content>
      <v-container class="fill-height" fluid>
        <v-row align="center" justify="center">
          <v-col class="text-center">
            <div id="container">
              <highcharts :options="chartOptions">Meu Grafico</highcharts>
            </div>
          </v-col>
        </v-row>
      </v-container>
    </v-content>
    <v-footer color="indigo" app>
      <span class="white--text">&copy; 2019.10</span>
    </v-footer>
  </v-app>
</template>


<script>
export default {
  data: () => ({
    chartOptions: {
      charttype: "spline",
      marginRight: 10,

      events: {
        load: function() {
          // set up the updating of the chart each second
          var series = this.series[0];
          setInterval(function() {
            var x = new Date().getTime(), // current time
              y = Math.random();
            series.addPoint([x, y], true, true);
          }, 1000);
        }
      },
      xAxis: {
        type: "datetime",
        tickPixelInterval: 150
      },
      yAxis: {
        title: {
          text: "Value"
        },
        plotLines: [
          {
            value: 0,
            width: 1,
            color: "#808080"
          }
        ]
      },
      tooltip: {
        headerFormat: "<b>{series.name}</b><br/>",
        pointFormat: "{point.x:%Y-%m-%d %H:%M:%S}<br/>{point.y:.2f}"
      },
      legend: {
        enabled: false
      },
      exporting: {
        enabled: false
      },
      series: [
        {
          name: "Random data",
          data: (function() {
            // generate an array of random data
            let data = [],
              time = new Date().getTime(),
              i;

            for (i = -19; i <= 0; i += 1) {
              data.push({
                x: time + i * 1000,
                y: Math.random()
              });
            }
            return data;
          })()
        }
      ]
    }
  })


};
</script>