#!/usr/bin/env python3

import re
import os
import sys
import math
import time
import random
from subprocess import Popen, PIPE

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

def shellout(cmd):
	print(' '.join(cmd))
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
		if os.path.exists('./daily.csv'):
			os.remove('./daily.csv')

		url = 'http://covidtracking.com/api/states/daily.csv'
		cmd = ['wget', url, '--output-document', './daily.csv']
		print(cmd)
		(stdout, stderr, ret_code) = shellout(cmd)

		if ret_code != 0:
			print('wget returned %d, retrying...' % ret_code)
			continue

		if os.path.getsize('./daily.csv') == 0:
			print('downloaded csv is 0 bytes, retrying...')
			continue

		break

# load the csv into the global data variable
def csv_load():
	global data

	lines = []
	with open('./daily.csv') as fp:
		lines = [x.strip() for x in fp.readlines()]

	if not lines[0].startswith('date,state,positive,negative'):
		raise Exception('unexpected csv header: %s' % lines[0])

	lines = lines[1:]

	for line in lines:
		fields = line.split(',')
		(date,state,positive,negative) = fields[0:4]
		if not state in data:
			data[state] = {}
		#print('appending %s (%s,%s)' % (state, date, positive))
		if positive == '': positive = 0
		if negative == '': negative = 0
		data[state][date] = {'positive':int(positive), 'negative':int(negative)}

	# check for missing dates
	now = time.time()
	nowstr = epochToISO8601(now).replace('-','')

	for state in state_abbrevs:
		dates = data[state].keys()

		earliest = min(dates)
		#print('%s earliest date is %s' % (state, earliest))
		m = re.match(r'^\d\d\d\d(\d\d)(\d\d)', earliest)

		cur = ISO8601ToEpoch('2020-%s-%s' % (m.group(1), m.group(2)))
		while cur < now:
			curstr = epochToISO8601(cur).replace('-','')
			if not curstr in dates and curstr != nowstr:
				raise Exception('%s has no data for %s' % (state, curstr))
			cur += 24*3600

	# generate 'US'
	earliest = latest = list(data['AK'].keys())[0]
	for state in state_abbrevs:
		earliest = min(earliest, min(data[state].keys()))
		latest = max(latest, max(data[state].keys()))
	print('latest date is: %s' % latest)
	m = re.match(r'^\d\d\d\d(\d\d)(\d\d)', earliest)
	cur = ISO8601ToEpoch('2020-%s-%s' % (m.group(1), m.group(2)))

	data['US'] = {}
	while cur < now:
		curstr = epochToISO8601(cur).replace('-','')
		positive_all_states = 0
		negative_all_states = 0
		for state in state_abbrevs:
			if not curstr in data[state]:
				continue
			positive_all_states += data[state][curstr]['positive']
			negative_all_states += data[state][curstr]['negative']
		if positive_all_states == 0: break
		data['US'][curstr] = {'positive':positive_all_states, 'negative':negative_all_states}
		cur += 24*3600

	state_abbrevs.append('US')
	state_names['US'] = 'United States'

def write_gnuplot(state):
	global data

	xtics = []
	positives = []
	for date in sorted(data[state]):
		# mm/dd
		xtics.append('%s/%s' % re.match(r'^\d\d\d\d(\d\d)(\d\d)$', date).group(1,2))
		positives.append(data[state][date]['positive'])

	(max_, min_) = (max(positives), min(positives))

	fpath = './gnuplot/%s.gnuplot' % state

	print('writing %s' % fpath)
	with open(fpath, 'w') as fp:
		fp.write('set term png\n')
		fp.write('set output "./graphs/%s.png\n' % (state))
		fp.write('set style data linespoints\n')
		fp.write('set key box opaque\n')
		fp.write('set style line 1 lt 2 lw 9 pt 9 ps 0.5\n')
		fp.write('set xtics rotate by -90\n')
		fp.write('set xtics font \',10\'\n')
		#fp.write('set bmargin 2\n')
		fp.write('set lmargin 8\n')
		#fp.write('set rmargin 0\n')
		#fp.write('set tmargin 0\n')
		if max_ - min_ > 100:
			fp.write('set yrange [0:%d]\n' % int(1.3 * max_))

		# <index> <positives> <rate_increase> <date>
		# 0 116 0 "03/15"
		# 1 141 1.216 "03/16"
		# 2 186 1.319 "03/17"
		# 3 314 1.688 "03/18"
		# 4 390 1.242 "03/19"
		fp.write('$data << EOD\n')
		idx = 0
		for (i, positive) in enumerate(positives):
			if idx == 0 or positives[i]<8 or positives[i-1]==0:
				daily_rate_increase = 1
			else:
				daily_rate_increase = positives[i] / positives[i-1]
			fp.write('%d %d %f "%s"\n' % (idx, positive, daily_rate_increase, xtics[i]))
			idx += 1
		fp.write('EOD\n')

		fp.write('set multiplot layout 2,1\n')
		fp.write('set grid\n')
		fp.write('set key left top\n')
		fp.write('plot "$data" using 1:2:xtic("") title "positives" linecolor rgb "#0000FF", \\\n')

		# fit a growth curve
		idx_t1 = idx - 1
		idx_t0 = idx_t1 - 6
		#print('positives[%d] = %d' % (idx_t0, positives[idx_t0]))
		#print('positives[%d] = %d' % (idx_t1, positives[idx_t1]))
		factor_daily = (positives[idx_t1]/positives[idx_t0]) ** (1/6.0)
		#print('daily factor: %f' % factor_daily)
		doubling_rate = math.log(2, factor_daily)
		fp.write('"$data" using 1:($1 < %d ? 1/0 : ' % idx_t0)
		# week_ago_value * (1.1695 ** x) where x is [0,1,2,3,4,5,6]
		fp.write(    '%d * (%f ** ($1-%d)) ' % (positives[idx_t0], factor_daily, idx_t0))
		fp.write(') title "%1.1f day doubling" linecolor rgb "#FF0000", \\\n' % doubling_rate)

		# labels
		space = int(1.3*max_ / 20) if max_ - min_ > 100 else 1
		fp.write('"$data" using 0:2:(($1 == %d || $1 == %d) ? sprintf("%%d            ",$2) : "") with labels notitle textcolor rgb "#0000FF"\n' % (idx_t1, idx_t1))

		# second plot, rate of change
		fp.write('set key right top\n')
		fp.write('set yrange [1 : 1.75]\n')
		fp.write('plot "$data" using 1:3:xtic(4) title "daily rate increase" linecolor rgb "#0000FF"\n')


def html(states=state_abbrevs):
	global data

	state2total = {state:max([data[state][date]['positive'] for date in data[state].keys()]) for state in state_abbrevs}
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
				fp.write('        <b>%s</b>:<br>\n' % (state_names[state_abbrev]))
				fpath = './graphs/%s.png' % state_abbrev
				fp.write('        <img src=%s?mt=%d>\n' % (fpath, int(os.path.getmtime(fpath))))
				fp.write('      </td>\n')
				queue = queue[1:]
			fp.write('    </tr>\n')

		fp.write('  </table>\n')
		fp.write('\n')

		fp.write('  <p>Data comes from <a href="https://covidtracking.com/">The COVID Tracking Project</a> and their generous API. API is accessed with <a href="https://www.gnu.org/software/wget/">wget</a>. Graphs are drawn with <a href="http://www.gnuplot.info/">gnuplot</a>.</p>\n')
		fp.write('  <p>This project is open source: <a href="https://github.com/lwerdna/uscovidgraphs">https://github.com/lwerdna/uscovidgraphs</a></p>\n')
		fp.write('\n')

		fp.write('</html>\n')

if __name__ == '__main__':
	command = '' if not sys.argv[1:] else sys.argv[1]

	if command == 'update':
		csv_update()
		csv_load()

	elif command == 'graph':
		csv_load()

		if sys.argv[2:]:
			work = [sys.argv[2]]
		else:
			work = state_abbrevs

		for state in work:
			write_gnuplot(state)
			shellout(['gnuplot', './gnuplot/%s.gnuplot'%state])

	elif command == 'html':
		csv_load()
		html()
