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
			backgroundColor: 'none',
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

function make_line_chart(elemid, title, xaxis, yaxis, series, opts) {
	if (!opts) opts = { };
	
	for (var si in series) {
		var s = series[si];
		if (si == 0) {
			s.lineWidth = 1;
			s.marker = { symbol: "circle", radius: 2 };
			s.color = '#CB4B16';
		}
	}
	
	var chart = new Highcharts.Chart({
		chart: {
			renderTo: elemid,
			type: 'line',
			zoomType: 'xy',
			width: opts.width,
			height: opts.height,
			marginTop: title ? 30 : 5,
			marginBottom: title ? 70 : 30
		},
		title: {
			text: title
		},
		credits: { enabled: false },
		xAxis: {
			min: opts.xmin,
			max: opts.xmax,
			title: { text: xaxis, style: { fontSize: "10px", fontWeight: "normal", color: "black" } },
			labels: { style: { fontSize: "10px", fontWeight: "normal", color: "black" } },
			gridLineWidth: 1,
		},
		yAxis: {
			min: opts.ymin,
			max: opts.ymax,
			title: { text: yaxis, style: { fontSize: "10px", fontWeight: "normal", color: "black" } },
			labels: { style: { fontSize: "10px", fontWeight: "normal", color: "black" } },
			gridLineWidth: 1
		},
		tooltip: {
			formatter: opts.tooltip ? opts.tooltip : function() {
				return this.point.x + opts.xunit + ": " + this.point.y + opts.yunit;
			}
		},
		legend: {
			enabled: series.length > 1,
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
				}
			}
		},
		series: series
	});
	return chart;
}

