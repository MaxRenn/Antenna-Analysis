import logging
import argparse
import sys
import operator
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from numpy import array, sign, zeros
from scipy.interpolate import interp1d
from read_minik import *

# Define constants
SPEED_OF_LIGHT = 0.299792458 # In meters per nanosecond
NUMBER_OF_CHANNELS = 8

# Define the constants for the x axis
X_MIN = -2000
X_MAX = 100

# Define directories
directory = "/home/user/Desktop/rise/Antenna-Analysis"
input_file  = directory + "/databases/Measurement_20180713/WaveDump_20180713_144835.db"

# Define all plot objects
plot_file = directory + "/analysis/"
fig1 = plt.figure(figsize = (12, 10))
plot1 = fig1.add_subplot(3, 1, 1)
plot2 = fig1.add_subplot(3, 1, 2)
plot3 = fig1.add_subplot(3, 1, 3)
fig2 = plt.figure(figsize = (12, 10))
fig3 = plt.figure(figsize = (12, 16))
ax = Axes3D(fig3)

# Antenna polar plot
plot6 = plt.subplot(3, 1, 1, projection = 'polar')
plot6.set_rmax(np.pi / 2)
plot6.grid(True)
# Minik polar plot
plot7 = plt.subplot(3, 1, 2, projection = 'polar')
plot7.set_rmax(np.pi / 2)
plot7.grid(True)

plot8 = plt.subplot(3, 1, 3)

# plot9 = plt.subplot(4, 1, 4)

plt.subplots_adjust(hspace = 1)
cmap = plt.cm.get_cmap("gist_rainbow", NUMBER_OF_CHANNELS) # Automatically assigns a color to each channel

# Define global variables
time_list = [] # Stores the time of each channel's peak frequency value. The index corresponds to the channel (i.e. time_list[0] is the time for ch0).
amplitude_list = [] # Stores the peak amplitude of each channel. The index corresponds to the channel.
event_list = [] # Stores all potential radio events across all channels
sorted_channel_list = [] # Stores the channels in the order in which they peaked
#envelope_list = [] # Stores the envelopes of each channel
#mean_list = [] # Stores the mean value of each channel. The index corresponds to the channel.


'''
# Old coordinates
A0 = np.array([26.5, -9.00, 0.001])
A1 = np.array([0, 0, 0.])
A2 = np.array([-2.17, 8.63, 0.001])
A3 = np.array([4.05, 11.90, 0.001])
'''

# MiniK coordinate system
A0 = np.array([-9.5127, -1.3129, 0.001])
A1 = np.array([-0.3003, 24.6127, 0.001])
A2 = np.array([8.0528, 28.1278, 0])
A3 = np.array([11.3887, 20.8345, 0])


# Allows the creation of several loggers
file_formatter = logging.Formatter("%(asctime)s: %(name)s: %(levelname)-8s %(message)s")
console_formatter = logging.Formatter("%(name)s: %(levelname)-8s %(message)s")
def setup_logger(name, log_file, consol, level = logging.INFO):

    handler = logging.FileHandler(directory + "/analysis/" + log_file)        
    handler.setFormatter(file_formatter)
    
    logger = logging.getLogger(name)    
    logger.setLevel(level)
    logger.addHandler(handler)
    logging.getLogger("matplotlib").setLevel(logging.WARNING) # Suppresses matplotlib debug

    if consol == True:
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)    
        console.setFormatter(console_formatter)
        logger.addHandler(console)    
    
    return logger


event_logger = setup_logger("event_logger", "events.log", consol = True)
coincidence_logger = setup_logger("coincidence_logger", "coincidences.log", consol = False)
cosmic_ray_logger = setup_logger("cosmic_ray_logger", "cosmic.log", consol = False) # Logs all events which have a coinciding signal within -1000 ns and 0 ns

#Retrieved from https://stackoverflow.com/questions/34235530/python-how-to-get-high-and-low-envelope-of-a-signal
#Creates an envelope then plots it
def create_and_plot_envelope(time, chan_num, adcValues):
    s = adcValues #This is your noisy vector of values.

    q_u = zeros(s.shape)

    #Prepend the first value of (s) to the interpolating values. This forces the model to use the same starting point for both the upper and lower envelope models.
    u_x = [0,]
    u_y = [s[0],]

    #Detect peaks and troughs and mark their location in u_x,u_y,l_x,l_y respectively.
    for k in range(1,len(s)-1):
        if (sign(s[k]-s[k-1])==1) and (sign(s[k]-s[k+1])==1):
            u_x.append(k)
            u_y.append(s[k])

    #Append the last value of (s) to the interpolating values. This forces the model to use the same ending point for both the upper and lower envelope models.
    u_x.append(len(s)-1)
    u_y.append(s[-1])

    #Fit suitable models to the data. Here I am using cubic splines, similarly to the MATLAB example given in the question.
    u_p = interp1d(u_x,u_y, kind = 'cubic',bounds_error = False, fill_value=0.0)

    #Evaluate each model over the domain of (s)
    for k in range(0,len(s)):
        q_u[k] = np.real(u_p(k))

    #Plot everything
    chan_name = "ch" + str(chan_num)
    
    col = cmap(chan_num)
    plot3.plot(time, q_u, color = col, linewidth = 3, label = chan_name + " upper envelope")

    # Find peak coordinates
    index = np.where(q_u == np.max(q_u))[0][0] # Envelope index of peak ampltiude
    ind_y = q_u[index]

    # Build string of peak coordinates and list of times
    coords = "({:6.3f}".format(time[index]) + ", {:6.3f}".format(ind_y) + ")"
    time_list.append(time[index]) # Adds the time at which the channel's signal peaks
    amplitude_list.append(float(ind_y))
    event_logger.info("        Envelope peak coordinate: " + coords + "")

    return q_u


def find_channel_mean(cut):
    chan_mean = np.real(np.mean(cut))
    event_logger.info("        Mean value: {:6.3f}".format(chan_mean) + " mV")

    return chan_mean


def find_signals(row, time, env_list, mean_list, bin_range, timestamp):
    
    global time_list
    if True: #max(time_list) - min(time_list) <= 250:
        signal_found = False
        event_info = []
        event_list = []

        for chan_num, env in enumerate(env_list):
            chan_mean = np.mean(env)
            chan_max = np.max(env)
            mean_max_diff = chan_max - chan_mean

            for i in range(0, len(time) - bin_range):
                
                temp_mean = np.mean(np.real(env[i : (i + bin_range)]))
                temp_diff = temp_mean - chan_mean

                if (temp_diff > mean_max_diff * 0.5) and signal_found is False:
                    signal_found = True
                    signal_begin = time[i]

                else:
                    if ((temp_diff < mean_max_diff * 0.5) or (i == len(time) - bin_range - 1)) and signal_found is True:
                        signal_found = False
                        signal_end = time[i + bin_range]

                        if (signal_begin != time[0] and signal_end != time[-1]) and ((signal_end - signal_begin) < 300):
                            event_info.append(chan_num)
                            event_info.append(signal_begin)
                            event_info.append(signal_end)
                            event_list.append(event_info)
                            event_info = []
                            
        #Sort event_list by signal_begin
        sorted_event_list = sorted(event_list, key = operator.itemgetter(1))
        # print(event_list)
        # print(sorted_event_list)

        # Check for coincidence amongst the events
        event_logger.info("    Coinciding signals:")
        coincidence = False
        log_string = ""
        chans_with_c_event = [] # Will store channel numbers with coinciding event
        coincidence_list = [] # Will store information about the coinciding event

        for i, comp_event in enumerate(sorted_event_list):
            coincidence_list.append(comp_event)
            comp_event_chan = comp_event[0]
            comp_event_begin = comp_event[1]
            comp_event_end = comp_event[2]

            # Add initial event
            if len(chans_with_c_event) == 0:
                chans_with_c_event.append(comp_event_chan)
                event_begin = comp_event_begin # Marks the beginning of the event as the start of the first event

            if float(len(chans_with_c_event)) >= 0.5 * NUMBER_OF_CHANNELS:
                coincidence = True
                # Check if all channels coincide
                if len(chans_with_c_event) == NUMBER_OF_CHANNELS:
                    event_logger.info("        A coinciding signal was detected in channels " + str(chans_with_c_event) + " and begins at or around t {:.0f} ns".format(event_begin) + " and ends at or around t {:.0f} ns".format(comp_event_end))
                    coincidence_logger.info("    Event " + str(row) + ":")
                    coincidence_logger.info("        Event Timestamp (sec): " + str(timestamp))
                    coincidence_logger.info("        A coinciding signal was detected in channels " + str(chans_with_c_event) + " and begins at or around t {:.0f} ns".format(event_begin) + " and ends at or around t {:.0f} ns".format(comp_event_end))# + " ns ( of {:+07.3f}".format(cut[i + bin_range] + " mV)"))
                    if comp_event_begin >= -1500 and comp_event_end <= 0:
                        cosmic_ray_logger.info("    Event " + str(row) + ":")
                        cosmic_ray_logger.info("        Event Timestamp (sec): " + str(timestamp))
                        cosmic_ray_logger.info("        A coinciding signal was detected in channels " + str(chans_with_c_event) + " and begins at or around t {:.0f} ns".format(event_begin) + " and ends at or around t {:.0f} ns".format(comp_event_end))# + " ns ( of {:+07.3f}".format(cut[i + bin_range] + " mV)"))
                    reconstructed = get_antennas(coincidence_list, row, timestamp)
                    if reconstructed == True:
                        make_histogram(time, coincidence_list, bin_range)
                        make_heatmap(time, coincidence_list)

                    chans_with_c_event = []
                    coincidence_list = []
                    continue

                # Check if the remaining channels coincide
                if i != len(sorted_event_list) - 1:
                    next_event = sorted_event_list[i + 1]
                    next_event_chan = next_event[0]
                    next_event_begin = next_event[1]    
                
                    if next_event_chan not in chans_with_c_event and np.abs(next_event_begin - comp_event_begin) < 500:
                        chans_with_c_event.append(next_event_chan)
                        continue

                    else:
                        event_logger.info("        A coinciding signal was detected in channels " + str(chans_with_c_event) + " and begins at or around t {:.0f} ns".format(event_begin) + " and ends at or around t {:.0f} ns".format(comp_event_end))# + " ns ( of {:+07.3f}".format(cut[i + bin_range] + " mV)"))
                        coincidence_logger.info("    Event " + str(row) + ":")
                        coincidence_logger.info("        Event Timestamp (sec): " + str(timestamp))
                        coincidence_logger.info("        A coinciding signal was detected in channels " + str(chans_with_c_event) + " and begins at or around t {:.0f} ns".format(event_begin) + " and ends at or around t {:.0f} ns".format(comp_event_end))# + " ns ( of {:+07.3f}".format(cut[i + bin_range] + " mV)"))
                        if comp_event_begin >= -1500 and comp_event_end <= 0:
                            cosmic_ray_logger.info("    Event " + str(row) + ":")
                            cosmic_ray_logger.info("        Event Timestamp (sec): " + str(timestamp))
                            cosmic_ray_logger.info("        A coinciding signal was detected in channels " + str(chans_with_c_event) + " and begins at or around t {:.0f} ns".format(event_begin) + " and ends at or around t {:.0f} ns".format(comp_event_end))# + " ns ( of {:+07.3f}".format(cut[i + bin_range] + " mV)"))
                        reconstructed = get_antennas(coincidence_list, row, timestamp)
                        if reconstructed == True:
                            make_histogram(time, coincidence_list, bin_range)
                            make_heatmap(time, coincidence_list)
                        chans_with_c_event = []
                        coincidence_list = []
                        continue
                else:
                    if comp_event_chan not in chans_with_c_event and np.abs(sorted_event_list[i - 1][1] - comp_event_begin) < 500:
                        chans_with_c_event.append(comp_event_chan)

                    event_logger.info("        A coinciding signal was detected in channels " + str(chans_with_c_event) + " and begins at or around t {:.0f} ns".format(event_begin) + " and ends at or around t {:.0f} ns".format(comp_event_end))# + " ns ( of {:+07.3f}".format(cut[i + bin_range] + " mV)"))
                    coincidence_logger.info("    Event " + str(row) + ":")
                    coincidence_logger.info("        Event Timestamp (sec): " + str(timestamp))
                    coincidence_logger.info("        A coinciding signal was detected in channels " + str(chans_with_c_event) + " and begins at or around t {:.0f} ns".format(event_begin) + " and ends at or around t {:.0f} ns".format(comp_event_end))# + " ns ( of {:+07.3f}".format(cut[i + bin_range] + " mV)"))
                    if comp_event_begin >= -1500 and comp_event_end <= 0:
                        cosmic_ray_logger.info("    Event " + str(row) + ":")
                        cosmic_ray_logger.info("        Event Timestamp (sec): " + str(timestamp))
                        cosmic_ray_logger.info("        A coinciding signal was detected in channels " + str(chans_with_c_event) + " and begins at or around t {:.0f} ns".format(event_begin) + " and ends at or around t {:.0f} ns".format(comp_event_end))# + " ns ( of {:+07.3f}".format(cut[i + bin_range] + " mV)"))
                    reconstructed = get_antennas(coincidence_list, row, timestamp)
                    if reconstructed == True:
                        make_histogram(time, coincidence_list, bin_range)
                        make_heatmap(time, coincidence_list)
                    chans_with_c_event = [] 
                    coincidence_list = []
                    continue                        
                
            if i != len(sorted_event_list) - 1:
                next_event = sorted_event_list[i + 1]
                next_event_chan = next_event[0]
                next_event_begin = next_event[1]    
                
                if next_event_chan not in chans_with_c_event and np.abs(next_event_begin - comp_event_begin) < 500:
                    chans_with_c_event.append(next_event_chan)
                    continue

                else:
                    chans_with_c_event = []
                    coincidence_list = []
                    continue

        # Reset each list after use
        amplitude_list = []
        event_list = []
        time_list = []

        return coincidence
    else:
        # Reset each list after use
        amplitude_list = []
        event_list = []
        time_list = []

        return False

# Creates and prints a sorted list of the peak amplitude and time difference for each channel
def sort_channels(cut_list):
    global time_list
    global amplitude_list
    global sorted_channel_list

    difference_list = [0] * len(cut_list) # Stores the sequencial differences in TOA of the peak. The index corresponds to the channel.
    sorted_channel_list = sorted(range(len(time_list)), key = lambda k: time_list[k]) # Stores the channels in order of the signal's arrival time

    initial_time = min(time_list) # The first time at which a channel peaked
    event_logger.info("    The first envelope peaked at: " + "{:07.3f}".format(initial_time) + " ns in ch" + str(sorted_channel_list[0])) 
    event_logger.info("    The channels peaked in the following order: ")

    for channel in sorted_channel_list:
        time_difference = time_list[channel] - initial_time
        difference_list[channel] = int(time_difference)
        event_logger.info("        ch" + str(channel) + "    t: " + "{:+8.0f}".format(time_list[channel]) + " ns ({:+04.0f} ns)".format(time_difference) + " with an amplitude of " + "{:10.3f}".format(amplitude_list[channel]) + " mV")


def make_histogram(time, coincidence_list, bin_range):

    # Creates histo_list if this is the first iteration of the program
    if (time[1] - time[0] != 1):
        time = np.arange(time[0], time[-1] + 1, step = 1) # Must fix time so that it has tep of 1

    if "histo_list" not in globals():
        global histo_list
        histo_list = np.zeros((NUMBER_OF_CHANNELS, len(time)))

    if coincidence_list != None:
        for signal in coincidence_list:
            chan_num = signal[0]
            event_time = signal[1]
            event_index = np.where(time == event_time)[0][0]
            diff = event_index % bin_range
            event_index -= diff
            for b in range(0, bin_range):
                if (event_index + b) < len(time) - 1:
                    histo_list[chan_num][event_index + b] += 1

    for chan_num in range(0, NUMBER_OF_CHANNELS): 
        plot4 = fig2.add_subplot(NUMBER_OF_CHANNELS, 2, chan_num * 2 + 1)
        plot4.clear()

        col = cmap(chan_num)
        plot4.plot(time, histo_list[chan_num][:], label = "ch" + str(chan_num) + " histo", color = col)
        plot4.fill_between(time[:], histo_list[chan_num][:], y2 = 0, color = col)
        plot4.set_xlabel("Time (ns)")
        plot4.set_ylabel("Event Counts ") # (Bin = " + str(bin_range) + " ns)
        plot4.set_title("Channel " + str(chan_num) + " Histogram")
        plot4.set_xlim(time[0], time[len(time) - 1])
        plot4.set_ylim(0, np.max(histo_list) + 1)
        plot4.grid(1)


def make_heatmap(time, coincidence_list):

    if (time[1] - time[0] != 1):
        time = np.arange(time[0], time[-1] + 1, step = 1) # Must fix time so that it has a step of 1

    # Creates heat_list if this is the first iteration of the program
    if "heat_list" not in globals():
        global heat_list
        heat_list = np.zeros((NUMBER_OF_CHANNELS, len(time)))

    if coincidence_list != None:
        for signal in coincidence_list:
            chan_num = signal[0]
            event_time_begin = signal[1]
            event_time_end = signal[2]
            event_index = np.where(time == event_time_begin)[0][0]
            diff = int(event_time_end - event_time_begin)
            for d in range(0, diff):
                heat_list[chan_num][event_index + d] += 1

    for chan_num in range(0, NUMBER_OF_CHANNELS):
        plot5 = fig2.add_subplot(NUMBER_OF_CHANNELS, 2, chan_num * 2 + 2)
        plot5.clear()

        col = cmap(chan_num)
        heat_max = np.max(heat_list)
        heat_sum = np.sum(heat_list[chan_num][:])
        if heat_sum == 0:
            heat_sum = 1
            
        plot5.plot(time, heat_list[chan_num][:] / heat_sum, label = "ch" + str(chan_num) + " heatmap", color = col)
        plot5.fill_between(time[:], heat_list[chan_num][:] / heat_sum * 100, y2 = 0, color = col)
        plot5.set_xlabel("Time (ns)")
        plot5.set_ylabel("% of total") # Relative frequency
        plot5.set_title("Channel " + str(chan_num) + " Heatmap")
        plot5.set_xlim(time[0], time[len(time) - 1])
        plot5.set_ylim(0, (heat_max / heat_sum * 100) * 1.1)
        plot5.grid(1)


def make_polarmap(a_azimuth, a_zenith, m_azimuth, m_zenith, polarity):

    '''
    # Initialize everything if this is the first iteration of the program
    if "m_zenith_max" not in globals():

        global a_azimuths
        global a_zeniths
        global m_azimuths
        global m_zeniths
        global a_z
        global m_z
        global a_r
        global a_th
        global m_r
        global m_th
        
        a_azimuths = np.radians(np.linspace(0, 360, 361))
        a_zeniths = np.arange(0, 90.1, step = 0.1)
        m_azimuths = np.radians(np.linspace(0, 360, 361))
        m_zeniths = np.arange(0, 90.1, step = 0.1)

        a_z = np.zeros((a_azimuths.size, a_zeniths.size))
        m_z = np.zeros((m_azimuths.size, m_zeniths.size))
        a_r, a_th = np.meshgrid(a_zeniths, a_azimuths)
        m_r, m_th = np.meshgrid(m_zeniths, m_azimuths)

    print(a_azimuth)
    print(a_zenith)
    print(m_azimuth)
    print(m_zenith)
    print(int(np.floor(m_zenith * 100)))
    print(len(m_zeniths))

    a_z[int(np.floor(a_azimuth)), int(np.floor(a_zenith * 10))] += 1
    a_z[int(np.floor(a_azimuth)) + 1, int(np.floor(a_zenith * 10))] += 1
    a_z[int(np.floor(a_azimuth)) - 1, int(np.floor(a_zenith * 10))] += 1
    a_z[int(np.floor(a_azimuth)), int(np.floor(a_zenith * 10)) + 1] += 1
    a_z[int(np.floor(a_azimuth)), int(np.floor(a_zenith * 10)) - 1] += 1

    m_z[int(np.floor(m_azimuth)), int(np.floor(m_zenith * 10))] += 1
    m_z[int(np.floor(m_azimuth)) + 1, int(np.floor(m_zenith * 10))] += 1
    m_z[int(np.floor(m_azimuth)) - 1, int(np.floor(m_zenith * 10))] += 1
    m_z[int(np.floor(m_azimuth)), int(np.floor(m_zenith * 10)) + 1] += 1
    m_z[int(np.floor(m_azimuth)), int(np.floor(m_zenith * 10)) - 1] += 1

    plot6.pcolormesh(a_th, a_r, a_z)
    plot7.pcolormesh(m_th, m_r, m_z)    
    
    if m_zenith > m_zenith_max:
        m_zenith_max = m_zenith * 1.1
        print(m_zenith_max)
        m_zenith_label_nums = np.linspace(0, m_zenith_max, 6)
        m_zenith_label = []
        for num in m_zenith_label_nums:
            m_zenith_label.append(str(np.round(num * 57.2958, 2)))
        plot7.set_rticks(m_zenith_label_nums)
        plot7.set_yticklabels(m_zenith_label)
        plot7.set_rmax(m_zenith_max)
    '''
    
    if polarity == 'EVEN':
        plot6.scatter(a_azimuth, a_zenith, c = 'red', alpha = 0.3, s = 15)
    else:
        plot6.scatter(a_azimuth, a_zenith, c = 'blue', alpha = 0.3, s = 15)

    plot6.set_title('Antenna Polar Scatterplot\n')
    plot6.set_rticks(np.linspace(0, np.pi / 2, 7))
    plot6.set_yticklabels(['0', '15', '30', '45', '60', '75', '90'])
    plot6.grid(1) 

    plot7.scatter(m_azimuth, m_zenith, c = 'green', alpha = 0.3, s = 15)
    plot7.set_title('MiniK Polar Scatterplot\n')
    plot7.set_rticks(np.linspace(0, np.pi / 2, 7))
    plot7.set_yticklabels(['0', '15', '30', '45', '60', '75', '90'])
    plot7.grid(1)   


def make_diffplot(a_azimuth, minik_azimuth):

    if "angle_diff_list" not in globals():
        global angle_diff_list
        angle_diff_list = []

    angle_diff = int(np.floor(np.abs(a_azimuth - minik_azimuth)))
    # print(angle_diff)
    angle_diff_list.append(angle_diff)

    plot8.hist(angle_diff_list, bins = range(min(angle_diff_list), max(angle_diff_list) + 5, 5), color = "green")
    plot8.set_xlabel("Azimuth Difference (degrees)")
    plot8.set_ylabel("Counts")
    plot8.set_title("Difference Between Antenna and MiniK Azimuths")
    plot8.grid(1)

               
def make_time_plot(a_time, m_time):

    if "time_diff_list" not in globals():
        global time_diff_list
        time_diff_list = []

    time_diff = int(np.floor(np.abs(a_time - m_time)))
    # print(time_diff)
    time_diff_list.append(time_diff)
    print(len(time_diff_list))

    plot9.hist(time_diff_list, bins = range(min(time_diff_list), max(time_diff_list) + 2, 1), color = "orange")
    plot9.set_xlabel("Time difference (s)")
    plot9.set_ylabel("Counts")
    plot9.set_title("Difference between Antenna and MiniK Timestamps")
    plot9.grid(1)


def get_antennas(coincidence_list, event_num, timestamp):
    master_antenna_list = [A0, A1, A2, A3] # The master antenna list
    antenna_combos = []
    temp_combo = []
    time_list = [] # Stores the signal begin times where the index corresponds to the channel number
    temp_times = []
    odd_channel_nums = []
    even_channel_nums = []
    odd_channel_times = [] # Stores all of the begin times of the odd numbered channels
    even_channel_times = [] # Stores all of the begin times of the even numbered channels
    event_list = [] # Stores the event by channel number (event_list[0] corresponds to ch0)
    even_azimuth_means = []
    even_zenith_means = []
    odd_azimuth_means = []
    odd_zenith_means = []

    '''
    # Removes the bad channel (ch0)
    new_coincidence_list = [] # Stores the coincidence list without the bad channel
    for i, signal in enumerate(coincidence_list):
        chan = signal[0]
        if int(chan) != 0:
            new_coincidence_list.append(signal)
    '''

    event_list = sorted(coincidence_list, key = operator.itemgetter(0)) # Sorts the events by channel number
    # print(event_list)    

    # Split the channels with events into even and odd lists.
    for event in event_list:
        if event[0] % 2 == 0:
            even_channel_nums.append(event[0])
            even_channel_times.append(event[1])

        else:
            odd_channel_nums.append(event[0])
            odd_channel_times.append(event[1])

    print('Even channels: ' + str(even_channel_nums))
    print('Odd  channels: ' + str(odd_channel_nums))

    # Determine the antenna combinations for the even channels.
    if len(even_channel_nums) > 2:
        temp_combo = []

        # The case where all antennas have an event.
        if len(even_channel_nums) == 4:
            # The antenna combinations are hardcoded. There are four combinations.
            antenna_combos.append([A0, A1, A2])
            time_list.append([even_channel_times[0], even_channel_times[1], even_channel_times[2]])

            antenna_combos.append([A0, A1, A3])
            time_list.append([even_channel_times[0], even_channel_times[1], even_channel_times[3]])

            antenna_combos.append([A0, A2, A3])
            time_list.append([even_channel_times[0], even_channel_times[2], even_channel_times[3]])
            
            antenna_combos.append([A1, A2, A3])
            time_list.append([even_channel_times[1], even_channel_times[2], even_channel_times[3]])

        # The case where only three antennas have an event.
        else:
            for chan_num in even_channel_nums:
                temp_combo.append(master_antenna_list[int(chan_num / 2)])

            antenna_combos.append(temp_combo)
            time_list.append(even_channel_times)

    # Peform direction reconstruction for all even channel combos.
    event_logger.info('Performing reconstruction for ' + str(len(antenna_combos)) + ' antenna combination(s)')
    for i, combo in enumerate(antenna_combos):
        reconstructed, a_azimuth, a_zenith, mk_azimuth, mk_zenith = find_direction(combo, time_list[i], timestamp)
        if reconstructed == True:
            make_polarmap(a_azimuth / 57.2958, a_zenith / 57.2958, mk_azimuth / 57.2958, mk_zenith / 57.2958, 'EVEN')
            even_azimuth_means.append(a_azimuth)
            even_zenith_means.append(a_zenith)

    if len(even_azimuth_means) != 0:
        event_logger.info('        Even azimuth mean: {:5.2f}'.format(np.mean(even_azimuth_means)))
        event_logger.info('        Even zenith mean:  {:5.2f}'.format(np.mean(even_zenith_means)))


    # Reset the lists for the odd combinations
    antenna_combos = []
    time_list = []
    # Determine the antenna combinations for the odd channels.
    if len(odd_channel_nums) > 2:
        temp_combo = []
        
        # The case where all antennas have an event.
        if len(odd_channel_nums) == 4:
            # The antenna combinations are hardcoded. There are four combinations.
            antenna_combos.append([A0, A1, A2])
            time_list.append([odd_channel_times[0], odd_channel_times[1], odd_channel_times[2]])

            antenna_combos.append([A0, A1, A3])
            time_list.append([odd_channel_times[0], odd_channel_times[1], odd_channel_times[3]])

            antenna_combos.append([A0, A2, A3])
            time_list.append([odd_channel_times[0], odd_channel_times[2], odd_channel_times[3]])

            antenna_combos.append([A1, A2, A3])
            time_list.append([odd_channel_times[1], odd_channel_times[2], odd_channel_times[3]])

        # The case where only three antennas have an event.
        else:
            for chan_num in odd_channel_nums:
                temp_combo.append(master_antenna_list[int((chan_num - 1) / 2)])

            antenna_combos.append(temp_combo)
            time_list.append(odd_channel_times)

    # Peform direction reconstruction for all even channel combos.
    event_logger.info('Performing reconstruction for ' + str(len(antenna_combos)) + ' antenna combination(s)')
    for i, combo in enumerate(antenna_combos):
        reconstructed, a_azimuth, a_zenith, mk_azimuth, mk_zenith = find_direction(combo, time_list[i], timestamp)
        if reconstructed == True:
            make_polarmap(a_azimuth / 57.2958, a_zenith / 57.2958, mk_azimuth / 57.2958, mk_zenith / 57.2958, 'ODD')
            odd_azimuth_means.append(a_azimuth)
            odd_zenith_means.append(a_zenith)

    if len(odd_azimuth_means) != 0:
        event_logger.info('        Odd azimuth mean: {:5.2f}'.format(np.mean(odd_azimuth_means)))
        event_logger.info('        Odd zenith mean: {:5.2f}'.format(np.mean(odd_zenith_means)))


# Method derived from arXiv:1702.04902
def find_direction(antenna_combo, time_list, timestamp):

    event_logger.info("Attempting to reconstruct " + str(antenna_combo) + "...")
    # print(antenna_combo)
    # print(time_list)

    reconstructed = False # Returned value to determine if direction reconsruction was successful.
    azimuth = -1
    zenith = -1
    mk_azimuth = -1
    mk_zenith = -1

    antenna_list = antenna_combo

    # D is a unit vector
    D = ( np.cross( (antenna_list[1] - antenna_list[0]), (antenna_list[2] - antenna_list[0]) ) ) / ( np.linalg.norm( np.cross( (antenna_list[1] - antenna_list[0]), (antenna_list[2] - antenna_list[0]) ) ) )
    D_x = D[0]
    D_y = D[1]
    D_z = D[2]

    # print('Length of D: ' + str(np.linalg.norm(D)))

    A_tilde = np.zeros((3,3))
    xy_sqrt = np.sqrt(np.square(D_x) + np.square(D_y))
    A_tilde[0][0] = (D_x * D_z) / xy_sqrt
    A_tilde[0][1] = (D_y * D_z) / xy_sqrt
    A_tilde[0][2] = np.negative( xy_sqrt )
    A_tilde[1][0] = np.negative(D_y) / xy_sqrt
    A_tilde[1][1] = D_x / xy_sqrt
    A_tilde[2][0] = D_x
    A_tilde[2][1] = D_y
    A_tilde[2][2] = D_z
    
    r_prime = []
    for r in antenna_list:
        r_prime.append( A_tilde.dot(r) )

    d_x_prime = SPEED_OF_LIGHT * ( ( (time_list[0] - time_list[2]) * (r_prime[1][1] - r_prime[0][1]) ) - ( (time_list[0] - time_list[1]) * (r_prime[2][1] - r_prime[0][1]) ) ) / ( ( (r_prime[2][0] - r_prime[0][0]) * (r_prime[1][1] - r_prime[0][1]) ) - ( (r_prime[1][0] - r_prime[0][0]) * (r_prime[2][1] - r_prime[0][1]) ) ) 
    d_y_prime = SPEED_OF_LIGHT * ( ( (time_list[0] - time_list[1]) * (r_prime[2][0] - r_prime[0][0]) ) - ( (time_list[0] - time_list[2]) * (r_prime[1][0] - r_prime[0][0]) ) ) / ( ( (r_prime[2][0] - r_prime[0][0]) * (r_prime[1][1] - r_prime[0][1]) ) - ( (r_prime[1][0] - r_prime[0][0]) * (r_prime[2][1] - r_prime[0][1]) ) ) 
    
    # print('Dx\': ' + str(d_x_prime))
    # print('Dy\': ' + str(d_y_prime))

    d_z_prime = np.sqrt( 1 - np.square(d_x_prime) - np.square(d_y_prime) )
        
    #d_prime is a unit vector
    d_prime = np.array((d_x_prime, d_y_prime, d_z_prime))

    if np.linalg.norm(d_prime) >= 0.999 and np.linalg.norm(d_prime) < 1.0001:
        
        # d is a unit vector
        d = (np.linalg.inv(A_tilde)).dot(d_prime)
        # print("d: " + str(d))
        # print("length of d: " + str(np.linalg.norm(d_prime)))

        zenith = np.arccos(d[2]) 
        azimuth = np.arccos(d[0] / np.sin(zenith))

        zenith *= 57.2958
        azimuth *= 57.2958

        if d[1] > 0:
            azimuth = 360 - azimuth

        if d[2] < 0:
            zenith = 180 - zenith

        # Relates the antenna azimuth with true North.
        azimuth = (azimuth + 360 - 75) % 360

        if not np.isnan(azimuth):
            reconstructed = True

            event_logger.info("        Antenna Zenith:  {:5.2f}  degrees".format(zenith))
            event_logger.info("        Antenna Azimuth: {:5.2f}  degrees".format(azimuth))

            coincidence_logger.info("        Antenna Zenith:  {:5.2f}  degrees".format(zenith))
            coincidence_logger.info("        Antenna Azimuth: {:5.2f}  degrees".format(azimuth))            

            # try:
                # mk_event_num, mk_timestamp, mk_azimuth, mk_zenith = find_mk_event(timestamp)

            # except Exception as e:
                # cosmic_ray_logger.warning("        Error when reading MiniK data: " + str(e) + ". Skipping...")
                # print(e)

            # Convert mk_azimuth so that it is with respect to true North.
            mk_azimuth = (mk_azimuth + 360 - 75) % 360

            # Compares the minik angles to the antenna angles
            if True:#azimuth >= mk_azimuth - 15 and azimuth <= mk_azimuth + 15:
                event_logger.info("        MiniK   Zenith:  {:5.2f}  degrees".format(mk_zenith))
                event_logger.info("        MiniK   Azimuth: {:5.2f}  degrees".format(mk_azimuth))
                coincidence_logger.info("        MiniK   Zenith:  {:5.2f}  degrees".format(mk_zenith))
                coincidence_logger.info("        MiniK   Azimuth: {:5.2f}  degrees".format(mk_azimuth))

                # Checks that the event falls within the time range in which cosmic ray events would be found
                if time_list[0] >= -2000 and time_list[-1] <= 0:
                    cosmic_ray_logger.info("        Antenna Zenith:  {:5.2f}  degrees".format(zenith))
                    cosmic_ray_logger.info("        Antenna Azimuth: {:5.2f}  degrees".format(azimuth))

                    cosmic_ray_logger.info("        MiniK   Zenith:  {:5.2f}  degrees".format(mk_zenith))
                    cosmic_ray_logger.info("        MiniK   Azimuth: {:5.2f}  degrees".format(mk_azimuth))

            make_diffplot(azimuth, mk_azimuth)
            # make_time_plot(timestamp, mk_timestamp)

        else:
            event_logger.info("...Failed.\n")
    
    else:
        event_logger.info("...Failed.\n")

    return reconstructed, azimuth, zenith, mk_azimuth, mk_zenith



# Searches for coincidence amongst channels
def analyze_channels(row, time, cut_list, bin_range, timestamp):

    channel_envelopes = [] # Stores the channel envelopes. Index corresponds to channel number
    channel_means = [] # Stores the channel means. Index corresponds to channel number

    time_cut = np.round(time) # Rounds each value to an int (each value is originally a float)
    x_min_index = np.where(time_cut == X_MIN)[0][0] # Returns time index of X_MIN
    x_max_index = np.where(time_cut == X_MAX)[0][0] + 1 # Returns time index of X_MAX
    time_cut = time_cut[x_min_index : x_max_index] # Cuts the time array down to only what will be analyzed
    
    # Analyze each channel separately
    for channel_number, cut in enumerate(cut_list):
        event_logger.info("    Channel " + str(channel_number) + ":")
        channel_means.append(find_channel_mean(cut)) # Finds mean of the channel cut
        channel_envelopes.append(create_and_plot_envelope(time_cut, channel_number, cut[x_min_index : x_max_index]))

    sort_channels(cut_list)
    coincidence = find_signals(row, time_cut, channel_envelopes, channel_means, bin_range, timestamp)
    
    return coincidence
