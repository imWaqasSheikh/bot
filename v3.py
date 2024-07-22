import pandas as pd
import matplotlib.pyplot as plt

# Sample data
data = {
    'Date': ['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', '2023-01-05', '2023-01-06'],
    'Open': [100, 102, 101, 103, 104],
    'High': [105, 106, 104, 108, 107],
    'Low': [99, 101, 100, 102, 103],
    'Close': [104, 105, 102, 106, 105]
}
df = pd.DataFrame(data)
df['Date'] = pd.to_datetime(df['Date'])
df.set_index('Date', inplace=True)

# Heikin Ashi calculations
df['HA_Close'] = (df['Open'] + df['High'] + df['Low'] + df['Close']) / 4

df['HA_Open'] = 0
df['HA_Open'].iloc[0] = (df['Open'].iloc[0] + df['Close'].iloc[0]) / 2
for i in range(1, len(df)):
    df['HA_Open'].iloc[i] = (df['HA_Open'].iloc[i-1] + df['HA_Close'].iloc[i-1]) / 2

df['HA_High'] = df[['High', 'HA_Open', 'HA_Close']].max(axis=1)
df['HA_Low'] = df[['Low', 'HA_Open', 'HA_Close']].min(axis=1)

# Plotting
fig, ax = plt.subplots()
for idx, row in df.iterrows():
    color = 'green' if row['HA_Close'] >= row['HA_Open'] else 'red'
    ax.plot([idx, idx], [row['HA_Low'], row['HA_High']], color='black')
    ax.plot([idx, idx], [row['HA_Open'], row['HA_Close']], color=color, linewidth=4)

ax.xaxis_date()
plt.title('Heikin Ashi Candlestick Chart')
plt.xlabel('Date')
plt.ylabel('Price')
plt.show()
