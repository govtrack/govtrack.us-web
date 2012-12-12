var party_colors = {
	'Democrat': 'rgba(20, 20, 255, .75)',
	'Republican': 'rgba(255, 20, 20, .75)',
	'Independent': 'rgba(100, 100, 100, .85)'
};

function make_sponsorship_chart(elemid, title, series, with_data_labels) {
	for (var si in series) {
		series[si].dataLabels = { enabled: with_data_labels, formatter: function() { return this.point.name; } };
	}
	
	for (var si in series) {
		var s = series[si];
		if (s.type == "highlight") {
			s.marker = { symbol: "triangle", radius: 7 };
			s.color = 'rgba(223, 83, 223, 1)';
			s.type = null;
		}
		if (s.type == "party") {
			s.marker = { symbol: "circle", radius: 3 };
			s.color = party_colors[s.party];
			s.name = s.party + "s";
			s.type = null;
			s.party = null;
		}
	}
	
	var chart = new Highcharts.Chart({
		chart: {
			renderTo: elemid,
			type: 'scatter',
			zoomType: 'xy',
			height: 350,
			marginTop: title ? 30 : 5,
			marginBottom: title ? 70 : 0
		},
		title: {
			text: title
		},
		credits: { enabled: false },
		xAxis: {
			title: { text: 'Ideology Score' },
			labels: { enabled: false },
			gridLineWidth: 1
		},
		yAxis: {
			min: 0,
			title: { text: 'Leadership Score' },
			labels: { enabled: false }
		},
		tooltip: {
			formatter: function() {
				return this.point.name;
			}
		},
		legend: {
			layout: 'horizontal',
			align: 'center',
			verticalAlign: title ? 'bottom' : 'top'
		},
		plotOptions: {
			scatter: {
				marker: {
					states: {
						hover: {
							enabled: true,
							lineColor: 'rgb(100,100,100)'
						}
					}
				},
				states: {
					hover: {
						marker: {
							enabled: false
						}
					}
				}
			}
		},
		series: series
	});
	return chart;
}
