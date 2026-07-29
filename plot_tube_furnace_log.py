import pandas as pd 
import matplotlib.pyplot as plt 
import datetime as dt
import matplotlib.dates as mdates


def plot_log_file(csv_path):
    df = pd.read_csv(csv_path)

    timestamp = df['timestamp']
    time = [dt.datetime.fromtimestamp(ts) for ts in timestamp]


    T1 = df['zone_1_temperature_c']
    T2 = df['zone_2_temperature_c']
    T3 = df['zone_3_temperature_c']

    fig,ax1 = plt.subplots(1,1)
    ax2 = ax1.twinx()

    ax1.plot(time,T1,color='tab:gray')
    ax1.plot(time,T2,color='tab:gray')
    ax1.plot(time,T3,color='tab:gray')

    ax2.plot(time,df['Ar_sccm'],color='tab:green',label="Ar")
    ax2.plot(time,df['H2S_sccm'],color='tab:orange',label="H2S")

    # plt.xticks(time[0::10])
    ax1.tick_params(axis='x',rotation=25)

    date_format = mdates.DateFormatter('%Y-%m-%d %H:%M')
    ax1.xaxis.set_major_formatter(date_format)

    ax1.set_ylabel('Temperature (C)')
    ax2.set_ylabel('Flow (sccm)')
    plt.legend()

    plt.savefig(csv_path.split(".")[0])
