#!/usr/bin/env python3

import re
import os
import sys
import time
import random
from subprocess import Popen, PIPE

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

def initialize_csvs():
	for state in state_abbrevs:
		state_done = False
		got_first = False

		for month in range(2,12+1):
			if state_done: break

			for day in range(1,31+1):
				if state_done: break

				date_code = '2020%02d%02d' % (month, day)
				fpath_csv = './csvs/%s-%s.csv' % (state, date_code)
				if os.path.exists(fpath_csv):
					continue
				url = 'https://covidtracking.com/api/states/daily.csv?state=%s&date=%s' % (state, date_code)
				cmd = ['wget', url, '--output-document', fpath_csv]
				print(cmd)
				(stdout, stderr, ret_code) = shellout(cmd)

				# error can come from wget or the file itself
				error = False
				if ret_code != 0:
					error = True
				else:
					with open(fpath_csv) as fp:
						if fp.read().startswith('error'):
							error = True
					if error:
						os.remove(fpath_csv)

				# initial errors are ok, but an error after we've gotten our first csv means we're done
				if error:
					if got_first:
						state_done = True
				else:
					got_first = True

def update_csvs(states=state_abbrevs):
	now = time.time()

	csvs = os.listdir('./csvs')
	for state in states:
		latest = sorted([x for x in csvs if x.startswith(state + '-')])[0]
		m = re.match(r'^..-2020(..)(..).csv', latest)
		(month_start, day_start) = map(int, m.group(1,2))
		print('starting %s at 2020%02d%02d' % (state, month_start, day_start))

		cur = ISO8601ToEpoch('2020-%02d-%02d' % (month_start, day_start))
		while cur < now:
			
			(month, day) = re.match(r'2020-(..)-(..)', epochToISO8601(cur)).group(1,2)
			date_code = '2020%s%s' % (month, day)
			fpath_csv = './csvs/%s-%s.csv' % (state, date_code)
			cur += 24*3600

			if os.path.exists(fpath_csv):
				print('%s exists, skipping download' % fpath_csv)
				continue
			url = 'https://covidtracking.com/api/states/daily.csv?state=%s&date=%s' % (state, date_code)
			cmd = ['wget', url, '--output-document', fpath_csv]
			print(cmd)
			(stdout, stderr, ret_code) = shellout(cmd)

			# error can come from wget or the file itself
			if ret_code != 0:
				continue

			# delete files that show error
			delete = False
			with open(fpath_csv) as fp:
				if fp.read().startswith('error'):
					delete = True
			if os.path.getsize(fpath_csv) == 0:
				delete = True
			if delete:
				os.remove(fpath_csv)

def csv_get(fname, key):
	fpath = './csvs/' + fname
	lookup = {}
	print('opening %s' % fpath)
	with open(fpath) as fp:
		for line in fp.readlines():
			(k, v) = line.split(',')
			v = v.strip()
			if not v:
				v = 0
			lookup[k] = v
	return lookup[key]

def write_gnuplot(state, positives, xtics):
	global min_points_doubler
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

		space = int(1.3*max_ / 20) if max_ - min_ > 100 else 1
		fp.write('"$data" using 0:($2+%d):(sprintf("%%d",$2)) with labels notitle textcolor rgb "#0000FF"\n' % space)

def get_state_positives(state):
	csvs = os.listdir('./csvs')
	batch = sorted([x for x in csvs if x.startswith(state + '-')])

	positives = []
	for fname in batch:
		positives.append(int(csv_get(fname, 'positive')))

	return positives

def graph(states=state_abbrevs):
	csvs = os.listdir('./csvs')
	for state in states:
		positives = get_state_positives(state)

		xtics = []
		for fname in sorted([x for x in csvs if x.startswith(state + '-')]):
			xtics.append('%s/%s' % re.match(r'^..-2020(..)(..)\.csv$', fname).group(1,2))

		write_gnuplot(state, positives, xtics)

		shellout(['gnuplot', './gnuplot/%s.gnuplot' % state])

def html(states=state_abbrevs):
	state2total = {}
	for state in states:
		positives = get_state_positives(state)
		state2total[state] = sorted(positives)[-1]

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

	if command == 'init':
		initialize_csvs()
	elif command == 'update':
		update_csvs()
	elif command == 'graph':
		graph()
	elif command == 'html':
		html()
