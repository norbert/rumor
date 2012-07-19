import datetime
import numpy as np
import matplotlib.pyplot as plt
import util
import colorsys

from gexf import Gexf
from math import log
from subprocess import call
from timeseries import *

def compute_rumor_tree_edges(statuses, edges, window):
  rumor_edges=[]
  parent={}
  for edge in edges:
    u = edge[0]
    v = edge[1]
    status_v = statuses[v]
    status_u = statuses[u]
    if status_v == None or status_u == None:
      continue
    if len(status_v) < 4 or len(status_u) < 4:
      continue
    if status_v[3] == '' or status_u[3] == '':
      continue
    # Compare timestamps
    try:
      t_v = util.datetime_to_epoch_seconds(status_v[3])
      t_u = util.datetime_to_epoch_seconds(status_u[3])
    except ValueError:
      print "Can't convert one or both of these to a timestamp:\n", status_v[3], '\n', status_u[3]
    t_diff = t_u - t_v
    if t_diff <= window and t_diff > 0:
      if u not in parent:
        parent[u] = (v, t_v, t_u)
      else:
        parent_u = parent[u]
        # Replace parent if there is a more recent parent
        if t_v > parent_u[1]:
          parent[u] = (v, t_v, t_u)
    elif -t_diff <= window and t_diff < 0:
      if v not in parent:
        parent[v] = (u, t_u, t_v)
      else:
        parent_v = parent[v]
        # Replace parent if there is a more recent parent
        if t_u > parent_v[1]:
          parent[v] = (u, t_u, t_v)

  rumor_edges = [ (parent[a][0],a,parent[a][2]) for a in parent ]
  for r in rumor_edges:
    print r
  rumor_edges.sort(util.timestamped_edge_comparator)
  return rumor_edges


# An edge (v,u) is a rumor edge iff (u,v) is in edges (i.e. u follows
# v) and if t_u - t_v <= window
def compute_rumor_edges(statuses, edges, window):
  rumor_edges = []
  for edge in edges:
    u = edge[0]
    v = edge[1]
    status_v = statuses[v]
    status_u = statuses[u]
    if status_v == None or status_u == None:
      continue
    if len(status_v) < 4 or len(status_u) < 4:
      continue
    if status_v[3] == '' or status_u[3] == '':
      continue
    # Compare timestamps
    try:
      t_v = util.datetime_to_epoch_seconds(status_v[3])
      t_u = util.datetime_to_epoch_seconds(status_u[3])
    except ValueError:
      print "Can't convert one or both of these to a timestamp:\n", \
        status_v[3], '\n', status_u[3]
    t_diff = t_u - t_v
    if t_diff <= window and t_diff > 0:
      rumor_edges.append((v, u, t_u))
    elif -t_diff <= window and t_diff < 0:
      rumor_edges.append((u, v, t_v))

  rumor_edges.sort(util.timestamped_edge_comparator,'descend')
  return rumor_edges

# Take statuses and edges sorted by timestamp and simulate the rumor
# forward in time.
def simulate(rumor, step_mode = 'time', step = 10, limit = 2400):
  rumor_edges = rumor['edges']
  rumor_statuses = rumor['statuses']
  trend_onset = rumor['trend_onset']

  # Figure
  plt.figure()

  # Time series
  max_sizes = []
  total_sizes = []
  component_nums = []
  entropies = []
  max_component_ratios = []
  timestamps = []

  min_time = min([ edge[2] for edge in rumor_edges ])
  if step_mode == 'time':
    next_time = min_time
  max_pos = limit

  print 'time\t\teid\t\tpos\t\t|C_max|\t\tN(C)\t\ttime-trend_onset'

  components = {}
  node_to_component_id = {}
  adj={}

  # Set to keep track of statuses that gain many inbound edges at the same
  # time. This happens when a user follows lots of people that have mentioned
  # the topic, then tweets about the topic gets all of those followees as
  # parents, causing a sharp spike in the component growth

  # spikeset = set()

  for eid, edge in enumerate(rumor_edges):
    # print edge
    # print components
    # print node_to_component_id

    # Update adjacency list
    if edge[0] in adj:
      adj[edge[0]].append(edge[1])
    else:
      adj[edge[0]]=[edge[1]]
    
    # Update components
    if edge[0] not in node_to_component_id and edge[1] not in \
        node_to_component_id:
      # Create new component with id edge[0] (i.e. first node belonging to that
      #  component)
      component_id = edge[0]
      # print 'Creating new component ', component_id, ' from ', edge[0], ' and
      # ', edge[1]
      members = set([edge[0], edge[1]])
      components[edge[0]] = members
      node_to_component_id[edge[0]] = component_id
      node_to_component_id[edge[1]] = component_id
    elif edge[0] not in node_to_component_id:
      c1 = node_to_component_id[edge[1]]
      # print 'Adding ', edge[0], ' to ', c1, ': ', components[c1]
      # raw_input('')
      components[c1].add(edge[0])
      node_to_component_id[edge[0]] = c1
    elif edge[1] not in node_to_component_id:
      c0 = node_to_component_id[edge[0]]
      # print 'Adding ', edge[1], ' to ', c0, ': ', components[c0]
      # raw_input('')
      components[c0].add(edge[1])
      node_to_component_id[edge[1]] = c0
    else:
      c0 = node_to_component_id[edge[0]]
      c1 = node_to_component_id[edge[1]]
      if c0 != c1:
        # Merge components.
        members = components[c1]
        # print 'Merging\n', c0, ': ', components[c0], '\ninto\n', c1, ': ',
        # components[c1], '\n' raw_input('')
        for member in components[c0]:
          members.add(member)
          node_to_component_id[member] = c1
        components.pop(c0)
    
    """
    # Pause when you have some number of repeat statuses in a row (meaning that
    # lots of edges that terminate in that status suddenly got created)
    repeat_num = 2
    status_id = rumor_statuses[rumor_edges[eid][1]][0]
    if eid > repeat_num and last_k_statuses_equal(status_id, rumor_statuses,rumor_edges, eid, repeat_num) and status_id not in spikeset:
      print (rumor_statuses[rumor_edges[eid][0]], rumor_statuses[rumor_edges[eid][1]])
      spikeset.add(status_id)
      raw_input()
    """

    if step_mode == 'index':
      pos = eid
    elif step_mode == 'time':
      pos = edge[2] - min_time
        
    if pos > limit:
      break

    if step_mode == 'index' and eid % step:
      continue
    if step_mode == 'time':
      if edge[2] < next_time:
        continue
      else:
        next_time = edge[2] + step

    component_sizes = []
    # raw_input('======================================================'
    for cid, members in components.items():
      component_sizes.append(len(members))
      # print 'component ', cid, ' size: ', len(members)  
      # raw_input('-------------------')

    time_after_onset = None
    if trend_onset is not None:
      time_after_onset = edge[2] - trend_onset

    print edge[2] - min_time, '\t\t', eid, '\t\t', pos, '/', limit, '\t\t', max(component_sizes), '\t\t', len(components), '\t\t', time_after_onset
    # Print largest adjacency list sizes.
    neighbor_counts=[ len(adj[k]) for k in adj ]
    sorted_idx=range(len(neighbor_counts))
    sorted_idx.sort(lambda x, y: neighbor_counts[y] - neighbor_counts[x])
    for itop in xrange(10):
      if itop>=len(sorted_idx):
        break
      print adj.keys()[sorted_idx[itop]], ':', neighbor_counts[sorted_idx[itop]]
    raw_input()

    # Desc sort of component sizes
    component_sizes.sort()
    component_sizes.reverse()

    # Append to timeseries
    max_sizes.append(max(component_sizes))
    total_sizes.append(sum(component_sizes))
    component_nums.append(len(component_sizes))
    entropies.append(util.entropy(component_sizes))
    if trend_onset is None:
      trend_onset = 0
    timestamps.append((edge[2] - trend_onset) / (60 * 60))
    max_component_ratios.append(float(max(component_sizes))/sum(component_sizes))
    shifted_ind = np.linspace(1, 1 + len(component_sizes), len(component_sizes))

    if eid > 0:
      color = util.step_to_color(pos, max_pos)
      plt.subplot(331)
      plt.loglog(shifted_ind, component_sizes, color = color, hold = 'on')
      plt.title('Loglog desc component sizes')

      plt.subplot(332)
      plt.semilogy(timestamps[-1], max_sizes[-1], 'ro', color = color, hold = 'on')
      plt.title('Max component size')
      plt.xlabel('time (hours)')

      plt.subplot(333)
      plt.semilogy(timestamps[-1], total_sizes[-1], 'ro', color = color, hold = 'on')
      plt.title('Total network size')
      plt.xlabel('time (hours)')

      plt.subplot(334)
      plt.plot(timestamps[-1], entropies[-1], 'go', color = color, hold = 'on')
      plt.title('Entropy of desc component sizes')
      plt.xlabel('time (hours)')

      plt.subplot(335)
      plt.semilogy(timestamps[-1], component_nums[-1], 'ko', color = color, hold = 'on')
      plt.title('Number of components')
      plt.xlabel('time (hours)')

      plt.subplot(336)
      plt.loglog(shifted_ind, np.cumsum(component_sizes), color = color, hold = 'on')
      plt.title('Cum. sum. of desc component sizes')

      plt.subplot(337)
      plt.plot(timestamps[-1], max_component_ratios[-1], 'ko', color = color, hold = 'on')
      plt.title('Max comp size / Total network Size')
      plt.xlabel('time (hours)')

    # plt.hist(component_sizes, np.linspace(0.5, 15.5, 15))
    # plt.plot(np.cumsum(np.histogram(component_sizes, bins = np.linspace(0.5,
    # 15.5, 15))[0]), hold = 'on')
    if not eid % 15*step:
      pass#plt.pause(0.001)
  plt.show()
  return components

def last_k_statuses_equal(equals_val, rumor_statuses, rumor_edges, curr_idx, k):
  for i in xrange(k):
    if rumor_statuses[rumor_edges[curr_idx-i][1]][0] is not equals_val:
      return False
  return True

#=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~
# DETECTION
#=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~=~

def detect(ts_info_pos, ts_info_neg):
  ts_info_pos_train = {}
  ts_info_pos_test = {}
  ts_info_neg_train = {}
  ts_info_neg_test = {}

  topics_pos = ts_info_pos.keys()
  topics_neg = ts_info_neg.keys()
  # Balance the data
  if len(ts_info_pos) > len(ts_info_neg):
    more_pos = True
    r = (len(ts_info_pos) - len(ts_info_neg)) / float(len(ts_info_pos))
    for topic in topics_pos:
      if np.random.rand() < r:
        ts_info_pos.pop(topic)
  else:
    more_pos = False
    r = (len(ts_info_neg) - len(ts_info_pos)) / float(len(ts_info_neg))
    topics = ts_info_neg.keys()
    for topic in topics_neg:
      if np.random.rand() < r:
        ts_info_neg.pop(topic)

  # Normalize all timeseries
  for topic in ts_info_pos:
    ts = ts_info_pos[topic]['ts']
    threshold = np.median(ts.values)
    normalized = np.array([ float(v + 0.01) / 
                            (threshold + 0.01) for v in ts.values])
    ts_info_pos[topic]['ts'] = Timeseries(ts.times, normalized)
    

  for topic in ts_info_neg:
    ts = ts_info_neg[topic]['ts']
    threshold = np.median(ts.values)
    normalized = np.array([ float(v + 0.01) / 
                            (threshold + 0.01) for v in ts.values])
    ts_info_neg[topic]['ts'] = Timeseries(ts.times, normalized)

  # Split into training and test
  topics_pos = ts_info_pos.keys()
  topics_neg = ts_info_neg.keys()
  test_frac = 0.05
  for topic in topics_pos:
    if np.random.rand() < test_frac:
      ts_info_pos_test[topic] = ts_info_pos.pop(topic)
  ts_info_pos_train = ts_info_pos
  for topic in topics_neg:
    if np.random.rand() < test_frac:
      ts_info_neg_test[topic] = ts_info_neg.pop(topic)
  ts_info_neg_train = ts_info_neg

  # Create positive and negative timeseries bundles
  bundle_pos = {}
  bundle_neg = {}
  detection_interval_time = 5 * 60 * 1000
  detection_window_time = 24 * detection_interval_time

  for topic in ts_info_pos_train:
    ts = ts_info_pos_train[topic]['ts']
    start = ts_info_pos_train[topic]['trend_start'] - detection_window_time
    end =  ts_info_pos_train[topic]['trend_start']
    tsw = ts.ts_in_window(start,end)
    bundle_pos[topic] = np.cumsum(tsw.values)
    
  for topic in ts_info_neg_train:
    ts = ts_info_neg_train[topic]['ts']
    start = ts.tmin + \
          np.random.rand() * (ts.tmax - ts.tmin - detection_window_time)
    end = start + detection_window_time
    tsw = ts.ts_in_window(start,end)
    bundle_neg[topic] = np.cumsum(tsw.values)

  # Training

  # Test
  tests = {'pos' : {'ts_info' : ts_info_pos_test, 'color' : 'b'},
           'neg' : {'ts_info' : ts_info_neg_test, 'color' : 'r'}}
  for type in tests:
    for topic in tests[type]['ts_info']:
      print '\nTopic: ', topic, '\t'
      indices_tested = set()
      ts_test = tests[type]['ts_info'][topic]['ts']
      t_window_starts = np.arange(ts_test.tmin,
          ts_test.tmax - detection_window_time - 2 * detection_interval_time,
          detection_interval_time)
      for t_window_start in t_window_starts:
        i_window_start = ts_test.time_to_index(t_window_start)
        # print 'Start index: ', i_window_start
        dt_detects = np.arange(detection_interval_time,
                               detection_window_time,
                               detection_interval_time)
        for dt_detect in dt_detects:
          di_detect = ts_test.dtime_to_dindex(dt_detect)
          i_detect = i_window_start + di_detect
          if i_detect in indices_tested:
            continue
          indices_tested.add(i_detect)

          # print 'Offset: ', di_detect, '\tAbsolute: ', (i_window_start + di_detect)

          test_val = np.sum(ts_test.values[i_window_start:i_window_start + di_detect])
          if dt_detect == max(dt_detects) and \
              t_window_start == max(t_window_starts):
            # Plot histogram of positive and negative values at i_window_start +
            # di_detect and vertical line for test value
            values_pos = [bundle_pos[t][di_detect] for t in bundle_pos]
            values_neg = [bundle_neg[t][di_detect] for t in bundle_neg]

            plt.hist([log(v) for v in values_pos],
                     bins = 25, hold = 'on', color = (0,0,1,0.5))
            plt.hist([log(v) for v in values_neg],
                     bins = 25, hold = 'on', color = (1,0,0,0.5))
            print 'Test value: ', log(test_val)
            plt.axvline(log(test_val), hold = 'on', color = tests[type]['color'])
            plt.show()
            
def detection_func(bundle_pos, bundle_neg, idx, test_val):
  vals_pos = [ bundle_pos[topic][idx] for topic in bundle_pos ]
  vals_neg = [ bundle_neg[topic][idx] for topic in bundle_neg ]
  inv_dists_pos = [ 1 / abs(test_val - v) for v in vals_pos ]
  inv_dists_neg = [ 1 / abs(test_val - v) for v in vals_neg ]
  return np.sum(inv_dists_pos) / np.sum(inv_dists_neg)

def viz_timeseries(ts_infos):
  colors = [(0,0,1), (1,0,0)]
  detection_window_time = 0.75 * 3600 * 1000
  bundles = {}
  for (i, ts_info) in enumerate(ts_infos):
    color = colors[i]
    bundles[i] = {}
    for (ti, topic) in enumerate(ts_info):
      ts = ts_info[topic]['ts']
      if ts_info[topic]['trend_start'] == 0 and ts_info[topic]['trend_end'] == 0:
        start = ts.tmin + \
          np.random.rand() * (ts.tmax - ts.tmin - detection_window_time)
        end = start + detection_window_time
      else:
        start = ts_info[topic]['trend_start'] - detection_window_time
        end =  ts_info[topic]['trend_start']
      
      # if np.random.rand() > 10.0 / len(ts_info.keys()):
      #   continue
      # if i == 0 and max(ts.values) < 50:
      #   continue
      
      threshold = np.median(ts.values)
      tsw = ts.ts_in_window(start,end)

      # normalized = np.array([max(v - threshold, 0) for v in tsw.values])
      normalized = np.array([ float(v + 0.01) / (threshold + 0.01) for v in tsw.values])

      bundles[i][topic] = Timeseries(tsw.times,
                                     [log(v) for v in np.cumsum(normalized)])

      plt.semilogy(np.array(tsw.times) - min(tsw.times),
               np.cumsum(normalized), hold = 'on', linewidth = 1, color = color)
      
      # plt.plot(np.array(tsw.times) - min(tsw.times),
      #          tsw.values, hold = 'on', linewidth = 1, color = color)
      
      """
      plt.plot(np.array(ts.times),
               ts.values, hold = 'on', linewidth = 1, color = color)
      plt.axvline(start, hold = 'on', color = 'k')
      plt.axvline(end, hold = 'on', color = 'k')
      """
      # plt.title(topic)
      # plt.show()
  plt.show()

  plot_hist = False
  if plot_hist:
    for time in np.linspace(0, detection_window_time - 1, 20):
      for i in bundles:
        hist = []
        for topic in bundles[i]:
          ts = bundles[i][topic]
          idx = ts.dtime_to_dindex(time)
          hist.append(ts.values[idx])
        n, bins, patches = plt.hist(hist, bins = 25, color = colors[i],
                                    normed = True, hold = 'on')
        plt.setp(patches, 'facecolor', colors[i], 'alpha', 0.25)
      plt.title(str((detection_window_time - time) / (60 * 1000)) + \
                ' minutes before onset')
      plt.show()

def build_gexf(edges, out_name, p_sample = 1):
  gexf = Gexf("snikolov", out_name)
  graph = gexf.addGraph('directed', 'dynamic', out_name)
  end = str(max([edge[2] for edge in edges]))
  for (src, dst, time) in edges:
    if np.random.rand() > p_sample:
      continue
    # Assumes time is in epoch seconds
    #d = datetime.datetime.fromtimestamp(int(time))    
    #date = d.isoformat()
    start = str(time)
    if not graph.nodeExists(src):
      graph.addNode(id = src, label = '', start = start, end = end)
    if not graph.nodeExists(dst):
      graph.addNode(id = dst, label = '', start = start, end = end)
    graph.addEdge(id = str(src) + ',' + str(dst), source = src,
                  target = dst, start = start, end = end)
  out = open('data/graphs/' + out_name + '.gexf', 'w')
  gexf.write(out)
  out.close()
