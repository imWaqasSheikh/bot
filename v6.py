import json
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, html, dcc
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import websocket
import threading
import time
import socket

# Create the Dash App
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

symbol_dropdown = html.Div([
    html.P('Symbol:'),
    dcc.Dropdown(
        id='symbol-dropdown',
        options=[{'label': 'BTC/USDT', 'value': 'btcusdt'}],
        value='btcusdt'
    )
])

timeframe_dropdown = html.Div([
    html.P('Timeframe:'),
    dcc.Dropdown(
        id='timeframe-dropdown',
        options=[{'label': '1m', 'value': '1m'}, {'label': '5m', 'value': '5m'}, {'label': '15m', 'value': '15m'}],
        value='1m'
    )
])

num_bars_input = html.Div([
    html.P('Number of Candles'),
    dbc.Input(id='num-bar-input', type='number', value='1000')
])

# Create the layout of the App
app.layout = html.Div([
    html.H1('Real Time Charts'),

    dbc.Row([
        dbc.Col(symbol_dropdown),
        dbc.Col(timeframe_dropdown),
        dbc.Col(num_bars_input)
    ]),

    html.Hr(),

    dcc.Interval(id='update', interval=1000),

    html.Div(id='page-content')

], style={'margin-left': '5%', 'margin-right': '5%', 'margin-top': '20px'})


# WebSocket setup
ws_data = []

def on_message(ws, message):
    global ws_data
    json_message = json.loads(message)
    kline = json_message['k']
    candle = {
        'time': pd.to_datetime(kline['t'], unit='ms'),
        'open': float(kline['o']),
        'high': float(kline['h']),
        'low': float(kline['l']),
        'close': float(kline['c'])
    }
    ws_data.append(candle)
    ws_data = ws_data[-1000:]  # Keep only the last 1000 candles

def on_error(ws, error):
    print("WebSocket error:", error)

def on_close(ws, close_status_code, close_msg):
    print("WebSocket closed, reconnecting...")
    time.sleep(5)  # Wait for 5 seconds before reconnecting
    start_websocket()

def on_open(ws):
    print("WebSocket connection opened")
    ws.send(json.dumps({
        "method": "SUBSCRIBE",
        "params": [
            "btcusdt@kline_1m"
        ],
        "id": 1
    }))

def start_websocket():
    while True:
        try:
            ws = websocket.WebSocketApp("wss://stream.binance.com:9443/ws",
                                        on_open=on_open,
                                        on_message=on_message,
                                        on_error=on_error,
                                        on_close=on_close)
            ws.run_forever()
        except socket.gaierror as e:
            print("Socket error:", e)
            time.sleep(5)  # Wait before retrying
        except Exception as e:
            print("Unexpected error:", e)
            time.sleep(5)  # Wait before retrying

# Start the WebSocket in a separate thread
ws_thread = threading.Thread(target=start_websocket)
ws_thread.start()


@app.callback(
    Output('page-content', 'children'),
    Input('update', 'n_intervals'),
    Input('symbol-dropdown', 'value'),
    State('timeframe-dropdown', 'value'), State('num-bar-input', 'value')
)
def update_ohlc_chart(interval, symbol, timeframe, num_bars):
    num_bars = int(num_bars)
    df = pd.DataFrame(ws_data)

    if df.empty:
        return [html.H2(id='chart-details', children='Waiting for data...')]

    # Calculate Heikin Ashi candles
    heikin_ashi_df = calculate_heikin_ashi(df)
    heikin_ashi_df = heikin_ashi_df.tail(num_bars)

    # Calculate SSL Strategy
    ssl_df = calculate_ssl_strategy(heikin_ashi_df)
    
    fig = go.Figure(data=go.Candlestick(x=ssl_df['time'],
                                        open=ssl_df['HA_Open'],
                                        high=ssl_df['HA_High'],
                                        low=ssl_df['HA_Low'],
                                        close=ssl_df['HA_Close']))

    # Add SSL Up and Down lines
    fig.add_trace(go.Scatter(x=ssl_df['time'], y=ssl_df['sslDown_Smooth'], mode='lines', line=dict(color='red'), name='SSL Down'))
    fig.add_trace(go.Scatter(x=ssl_df['time'], y=ssl_df['sslUp_Smooth'], mode='lines', line=dict(color='lime'), name='SSL Up'))

    fig.update(layout_xaxis_rangeslider_visible=False)
    fig.update_layout(yaxis={'side': 'right'})
    fig.layout.xaxis.fixedrange = True
    fig.layout.yaxis.fixedrange = True

    return [
        html.H2(id='chart-details', children=f'{symbol.upper()} - {timeframe}'),
        dcc.Graph(figure=fig, config={'displayModeBar': False})
    ]


def calculate_heikin_ashi(df):
    heikin_ashi_df = df.copy()
    heikin_ashi_df['HA_Close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
    heikin_ashi_df['HA_Open'] = 0.0  # Initialize column

    # Set the first HA Open value
    heikin_ashi_df.loc[0, 'HA_Open'] = (df['open'].iloc[0] + df['close'].iloc[0]) / 2

    # Calculate the remaining HA Open values
    for i in range(1, len(df)):
        heikin_ashi_df.loc[i, 'HA_Open'] = (heikin_ashi_df.loc[i - 1, 'HA_Open'] + heikin_ashi_df.loc[i - 1, 'HA_Close']) / 2

    heikin_ashi_df['HA_High'] = heikin_ashi_df[['HA_Open', 'HA_Close', 'high']].max(axis=1)
    heikin_ashi_df['HA_Low'] = heikin_ashi_df[['HA_Open', 'HA_Close', 'low']].min(axis=1)

    return heikin_ashi_df

def calculate_ssl_strategy(df, period=10, smoothing_period=5):
    df['smaHigh'] = df['HA_High'].rolling(window=period).mean()
    df['smaLow'] = df['HA_Low'].rolling(window=period).mean()
    df['Hlv'] = 0

    for i in range(1, len(df)):
        if df['HA_Close'].iloc[i] > df['smaHigh'].iloc[i]:
            df.at[i, 'Hlv'] = 1
        elif df['HA_Close'].iloc[i] < df['smaLow'].iloc[i]:
            df.at[i, 'Hlv'] = -1
        else:
            df.at[i, 'Hlv'] = df['Hlv'].iloc[i-1]

    df['sslDown'] = df.apply(lambda row: row['smaHigh'] if row['Hlv'] < 0 else row['smaLow'], axis=1)
    df['sslUp'] = df.apply(lambda row: row['smaLow'] if row['Hlv'] < 0 else row['smaHigh'], axis=1)
    
    # Apply EMA smoothing
    df['sslDown_Smooth'] = df['sslDown'].ewm(span=smoothing_period, adjust=False).mean()
    df['sslUp_Smooth'] = df['sslUp'].ewm(span=smoothing_period, adjust=False).mean()
    
    return df

if __name__ == '__main__':
    # Start the Dash server
    app.run_server(debug=True, port=8051)  # Specify a different port here
