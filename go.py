#!/usr/bin/env python3

import re
import os
import sys
import time
import random
from subprocess import Popen, PIPE

# { 'TX' -> {
#
#
# }
data = {}

state_abbrevs = [ \
'AK', 'AL', 'AR', 'AZ', 'CA', 'CO', 'CT', 'DC', 'DE', 'FL', 'GA',
'HI', 'IA', 'ID', 'IL', 'IN', 'KS', 'KY', 'LA', 'MA', 'MD', 'ME', 'MI', 'MN',
'MO', 'MS', 'MT', 'NC', 'ND', 'NE', 'NH', 'NJ', 'NM', 'NV', 'NY', 'OH',
'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VA', 'VT',
'WA', 'WI', 'WV', 'WY']
assert len(state_abbrevs) == 50+1

# covidtracking has data for, but we don't include, these:
# AS American Samoa
# GU Guam
# MP Northern Mariana Islands
# PR Puerto Rico
# VI Virgin Islands

state_names = {
'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA':
'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DC':'District of Columbia', 'DE': 'Delaware', 'FL':
'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN':
'Indiana', 'IA': 'Iowa', 'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME':
'Maine', 'MD': 'Maryland', 'MA': 'Massachusetts', 'MI': 'Michigan', 'MN':
'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri', 'MT': 'Montana', 'NE':
'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM':
'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH':
'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island',
'SC': 'South Carolina', 'SD': 'South Dakota', 'TN': 'Tennessee', 'TX':
'Texas', 'UT': 'Utah', 'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV':
'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming'
}

# the minimum data points >= 100 until the "doubler" mode of graphing activates
min_points_doubler = 6

def shellout(cmd):
	process = Popen(cmd, stdout=PIPE, stderr=PIPE)
	(stdout, stderr) = process.communicate()
	stdout = stdout.decode("utf-8")
	stderr = stderr.decode("utf-8")
	process.wait()
	return (stdout, stderr, process.returncode)

def epochToISO8601(epoch: float):
	timeStruct = time.localtime(epoch)
	timeString = time.strftime('%Y-%m-%d', timeStruct)
	return timeString

def ISO8601ToEpoch(isoString: str):
	timeStruct = time.strptime(isoString, '%Y-%m-%d')
	epoch = time.mktime(timeStruct)
	return epoch

# download the latest csv from covid tracking project using wget
def csv_update():
	while 1:
		if os.path.exists('/tmp/daily.csv'):
			os.remove('/tmp/daily.csv')

		url = 'http://covidtracking.com/api/states/daily.csv'
		cmd = ['wget', url, '--output-document', '/tmp/daily.csv']
		print(cmd)
		(stdout, stderr, ret_code) = shellout(cmd)

		if ret_code != 0:
			print('wget returned %d, retrying...' % ret_code)
			continue

		if os.path.getsize('/tmp/daily.csv') == 0:
			print('downloaded csv is 0 bytes, retrying...')
			continue

		break

# load the csv into the global data variable
def csv_load():
	global data

	lines = []
	with open('/tmp/daily.csv') as fp:
		lines = [x.strip() for x in fp.readlines()]

	assert lines[0] == 'date,state,positive,negative,pending,hospitalized,death,total,hash,dateChecked,totalTestResults,fips,deathIncrease,hospitalizedIncrease,negativeIncrease,positiveIncrease,totalTestResultsIncrease'
	lines = lines[1:]

	for line in lines:
		(date,state,positive,_,_,_,_,_,_,_,_,_,_,_,_,_,_) = line.split(',')
		if not state in data:
			data[state] = {}
		#print('appending %s (%s,%s)' % (state, date, positive))
		if positive == '': positive = 0
		data[state][date] = int(positive)

	# check for missing dates
	now = time.time()

	for state in state_abbrevs:
		dates = data[state].keys()

		earliest = min(dates)
		print('%s earliest date is %s' % (state, earliest))
		m = re.match(r'^\d\d\d\d(\d\d)(\d\d)', earliest)

		cur = ISO8601ToEpoch('2020-%s-%s' % (m.group(1), m.group(2)))
		nowstr = epochToISO8601(now).replace('-','')
		while cur < now:
			curstr = epochToISO8601(cur).replace('-','')
			if not curstr in dates and curstr != nowstr:
				raise Exception('%s has no data for %s' % (state, curstr))
			cur += 24*3600

def write_gnuplot(state):
	global data
	global min_points_doubler

	xtics = []
	positives = []
	for date in sorted(data[state]):
		# mm/dd
		xtics.append('%s/%s' % re.match(r'^\d\d\d\d(\d\d)(\d\d)$', date).group(1,2))
		positives.append(data[state][date])

	doubler = len([x for x in positives if x >= 100]) >= min_points_doubler

	if doubler:
		i = 0
		while positives[i] < 100:
			i += 1
		positives = positives[i:]
		xtics = xtics[i:]

	(max_, min_) = (max(positives), min(positives))

	fpath = './gnuplot/%s.gnuplot' % state

	print('writing %s' % fpath)
	with open(fpath, 'w') as fp:
		fp.write('set term png\n')
		fp.write('set output "./graphs/%s.png\n' % (state))
		fp.write('set style data linespoints\n')
		fp.write('set key box\n')
		fp.write('set style line 1 lt 2 lw 9 pt 9 ps 0.5\n')
		fp.write('set xtics rotate by -45\n')
		if max_ - min_ > 100:
			fp.write('set yrange [0:%d]\n' % int(1.3 * max_))

		# eg:
		# 0 116 "03/15"
		# 1 141 "03/16"
		# 2 186 "03/17"
		# 3 314 "03/18"
		# 4 390 "03/19"
		fp.write('$data << EOD\n')
		idx = 0
		for (i, positive) in enumerate(positives):
			fp.write('%d %d "%s"\n' % (idx, positive, xtics[i]))
			idx += 1
		fp.write('EOD\n')

		fp.write('set grid\n')
		fp.write('plot "$data" using 1:2:xtic(3) title "positives" linecolor rgb "#0000FF", \\\n')
		if doubler:
			fp.write('%d*2**(x/2.5) title "2.5 day doubling" linecolor rgb "#FF0000", \\\n' % positives[0])
			fp.write('%d*2**(x/3) title "3 day doubling" linecolor rgb "#FF0000", \\\n' % positives[0])

		space = int(1.3*max_ / 20) if max_ - min_ > 100 else 1
		fp.write('"$data" using 0:($2+%d):(sprintf("%%d",$2)) with labels notitle textcolor rgb "#0000FF"\n' % space)

def html(states=state_abbrevs):
	global data

	state2total = {state:max(data[state].values()) for state in state_abbrevs}
	worst2best = sorted(state2total, key=lambda x: state2total[x], reverse=True)
	for state in worst2best:
		print('state %s has %d cases' % (state, state2total[state]))

	with open('./index.html', 'w') as fp:
		fp.write('<!DOCTYPE html>\n')
		fp.write('<html lang="en">\n')
		fp.write('  <head>\n')
		fp.write('    <meta charset="utf-8">\n')
		fp.write('    <title>US covid graphs</title>\n')
		fp.write('    <style>\n')
		fp.write('      td {\n')
		fp.write('	      text-align: center;\n')
		fp.write('      }\n')
		fp.write('    </style>\n')
		fp.write('  </head>\n')
		fp.write('\n')
		fp.write('  <table>\n')

		queue = list(worst2best)
		while queue:
			fp.write('    <tr>\n')
			for i in range(2):
				if not queue:
					fp.write('      <td></td>\n');
					continue

				state_abbrev = queue[0]
				fp.write('      <td>\n')
				fp.write('        %s:<br>\n' % (state_names[state_abbrev]))
				fpath = './graphs/%s.png' % state_abbrev
				fp.write('        <img src=%s?mt=%d>\n' % (fpath, int(os.path.getmtime(fpath))))
				fp.write('      </td>\n')
				queue = queue[1:]
			fp.write('    </tr>\n')

		fp.write('  </table>\n')
		fp.write('\n')

		fp.write('  <p>Data comes from <a href="https://covidtracking.com/">The COVID Tracking Project</a> and their generous API. Graphs are drawn with <a href="http://www.gnuplot.info/">gnuplot</a>.</p>\n')
		fp.write('  <p>Once %d data points greater than 100 are available, those less than 100 are ignored and comparison is made with the 2.5 day doubling curve.</p>\n' % min_points_doubler)
		fp.write('  <p>This project is open source: <a href="https://github.com/lwerdna/uscovidgraphs">https://github.com/lwerdna/uscovidgraphs</a></p>\n')
		fp.write('\n')

		fp.write('</html>\n')

if __name__ == '__main__':
	command = '' if not sys.argv[1:] else sys.argv[1]

	if command == 'update':
		csv_update()
	elif command == 'load':
		csv_load()
	elif command == 'graph':
		csv_load()
		for state in state_abbrevs:
			write_gnuplot(state)
			shellout(['gnuplot', './gnuplot/%s.gnuplot'%state])

	elif command == 'html':
		csv_load()
		html()
