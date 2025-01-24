var chart = new Highcharts.Chart({
  chart: {
    renderTo: 'voting_record_chart_{{person.id}}',
    type: 'spline',
    height: 225,
    marginTop: 5,
  },
  title: { text: 'Missed Votes, {{missedvotes.firstdate|date}} - {{missedvotes.lastdate|date}}' },
  legend: { enabled: false },
  credits: { enabled: false },
  xAxis: {
    labels: { rotation: -90, align: "right" {% if missedvotes.data|length > 20 and missedvotes.data|length < 40 %}, step: 2{% endif %} {% if missedvotes.data|length >= 40 %}, step: 4{% endif %} },
    categories: [{% for rec in missedvotes.data %}"{{rec.time|escapejs}}"{% if not forloop.last %}, {% endif %}{% endfor %} ]
  },
  yAxis: {
    title: {
      text: 'Missed Votes (%)'
    },
    minorGridLineWidth: 0,
    gridLineWidth: 0,
    alternateGridColor: null,
    min: 0,
    {% if missed_votes_max_100 %}max: 100,
    {% else %}
    max: {% if missedvotes.max_percent >= 50 %}100{% else %}null{% endif %},
    plotBands: [{
      from: 0,
      to: {{missedvotes.pctile25}},
      color: 'rgba(68, 170, 213, 0.1)',
      label: {
        text: '25th Percentile',
        verticalAlign: 'top',
        style: { color: '#606060' }
      }
    }, {
      from: {{missedvotes.pctile25}},
      to: {{missedvotes.pctile50}},
      color: 'rgba(68, 170, 213, 0.3)',
      label: {
        text: 'Median',
        verticalAlign: 'top',
        style: { color: '#606060' }
      }
    }, {
      from: {{missedvotes.pctile50}},
      to: {{missedvotes.pctile75}},
      color: 'rgba(68, 170, 213, 0.1)',
      label: {
        text: '75th Percentile',
        verticalAlign: 'top',
        style: { color: '#606060' }
      }
    }, {
      from: {{missedvotes.pctile75}},
      to: {{missedvotes.pctile90}},
      color: 'rgba(68, 170, 213, 0.3)',
      label: {
        text: '90th Percentile',
        verticalAlign: 'top',
        style: { color: '#606060' }
      }
    }]
    {% endif %}
  },
  tooltip: {
    formatter: function() {
        return this.x +': '+ this.y +'% votes missed';
    }
  },
  plotOptions: {
    spline: {
      lineWidth: 2,
      marker: {
        radius: 3
      },
      states: {
        hover: {
          lineWidth: 2
        }
      }
    }
  },
  series: [{
    name: '{{person.lastname|escapejs }} - Missed Votes %',
    data: [{% for rec in missedvotes.data %}{{rec.percent}}{% if not forloop.last %}, {% endif %}{% endfor %} ]

  }],
  navigation: {
    menuItemStyle: {
      fontSize: '10px'
    }
  }
});
