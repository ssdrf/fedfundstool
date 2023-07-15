# -*- coding: utf-8 -*-

import os
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.io as pio
import plotly.graph_objects as go
from plotly.offline import plot
import yfinance as yf
from fredapi import Fred
from datetime import datetime
from datetime import timedelta
from dateutil.relativedelta import relativedelta

# Get your API key from environment variable
api_key = os.getenv('FRED_API_KEY')

# Check if API key is available
if not api_key:
    raise ValueError("No API key found. Please set your 'FRED_API_KEY' environment variable")

# Fetch data from the Federal Reserve Economic Data (FRED)
fred = Fred(api_key=api_key)

# Retrieve data series from Fred API for different market instruments, each for last two years
rrp = fred.get_series('RRPONTSYAWARD').tail(365*2)
ioer = fred.get_series('IORB').tail(365*2)
ioer_disc = fred.get_series('IOER')
ioer_full = pd.concat([ioer_disc, ioer]).tail(365*2)
eff = fred.get_series('DFF').tail(365*2)
eff_hist = fred.get_series('FEDFUNDS').tail(365*2)
sp = fred.get_series('SP500').tail(365*2)
dwr = fred.get_series('DPCREDIT').tail(365*2)
dot = fred.get_series('FEDTARMD').tail(365*2)
sofr = fred.get_series('SOFR')
sofr = sofr.fillna(method = 'pad').tail(365*2)  # Fill any missing data using previous value

# Get current and next year (in two digit format)
current_year = datetime.now().year % 100
next_year = (current_year + 1) % 100

# Prepare ticker symbols for next 24 months using months' futures contract symbols and current & next years
months = ['F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z']
tickers = [f'ZQ{x}{year}.CBT' for year in [current_year, next_year] for x in months]

# Function to download ticker data using Yahoo Finance API
def download_data(ticker):
    try:
        return yf.download(ticker, progress=False)
    except Exception as e:
        print(f'Failed to download {ticker}: {e}')
        return None

# Download data for each ticker and store it in a dictionary
ticker_data = {}
for ticker in tickers:
    data = download_data(ticker)
    if data is not None:
        data = data.loc[(datetime.now() - 5*timedelta(days=365)).strftime('%Y-%m-%d'):].copy()
        data['Adj Close'] = data['Adj Close']
        data['Ticker'] = ticker
        ticker_data[ticker] = data

# Consolidate all ticker data into a single dataframe
df_list = []
for ticker, data in ticker_data.items():
    if data is not None and not data.empty:
        data = data.loc[(datetime.now() - 5*timedelta(days=365)).strftime('%Y-%m-%d'):]
        data.loc[:, 'Adj Close'] = 100 - data['Adj Close']  # Adjust close price
        data.loc[:, 'Ticker'] = ticker
        df_list.append(data)

df = pd.concat(df_list)

# Function to get close price 'days_ago' from current date for a given ticker
def get_last_close_price(ticker_data, days_ago=1):
    data = ticker_data
    if data is not None and len(data) >= days_ago:
        return data['Adj Close'][-days_ago]
    return None

# Get last week's and today's implied term structure for each contract
forward = {}
forward_week_ago = {}
start_month = 2
start_year = current_year

for i, ticker in enumerate(tickers):
    data = ticker_data[ticker]
    last_close_price = get_last_close_price(data)
    last_close_price_week_ago = get_last_close_price(data, 8)
    if last_close_price is not None or last_close_price_week_ago is not None:
        contract_end_date = datetime(start_year, start_month, 1) + relativedelta(months=i)
        if last_close_price is not None:
            forward[contract_end_date.strftime('%Y-%m-%d')] = last_close_price
        if last_close_price_week_ago is not None:
            forward_week_ago[contract_end_date.strftime('%Y-%m-%d')] = last_close_price_week_ago

forward = pd.Series(data=forward)
forward_week_ago = pd.Series(data=forward_week_ago)

# Create Figure
fig = go.Figure()

for ticker in df['Ticker'].unique()[::-1]:
    fig.add_trace(go.Scatter(x=df[df['Ticker'] == ticker].index,
                             y=df[df['Ticker'] == ticker]['Adj Close'],
                             name=ticker,
                             visible='legendonly',
                             showlegend=True))



# Update layout settings
fig.update_layout(template='plotly_dark');
fig.update_layout(height=600,width=1000,font=dict(family="Roboto Mono",size=11));
fig.update_layout(title =f"fed funds futures   (Updated: {now_utc()})",title_y=0.95,title_x=0.08);
fig.update_xaxes(showline=True, linewidth=1, linecolor='white', mirror=True,ticks='outside');
fig.update_yaxes(showline=True, linewidth=1, linecolor='white', mirror=True,ticks='outside');
fig.update_layout(scene = dict(xaxis_title='Year', yaxis_title='Rate'));

# Add traces for other market instruments and implied term structure to the figure
fig.add_trace(go.Scatter(x=rrp.index, y=rrp.values, name='O/N RRP', opacity=1, line=dict(color='#075E45', width=2, dash='dash')))
fig.add_trace(go.Scatter(x=ioer_full.index, y=ioer_full.values, name='IOER', opacity=1, line=dict(color='#75160C', width=2, dash='dash')))
fig.add_trace(go.Scatter(x=sofr.index, y=sofr.values, name='SOFR', line=dict(color='darkgreen', width=2), opacity=.5))
fig.add_trace(go.Scatter(x=eff.index, y=eff.values, name='EFF', line=dict(color='White', width=2), opacity=.8))
fig.add_trace(go.Scatter(x=dot.index, y=dot.values, name='FOMC Dots Median', line=dict(color='#ffcc00', width=2, dash='dash'), opacity=.8, mode='lines+markers', marker_symbol='cross', marker=dict(size=6, color='#ffcc00')))

fig.add_trace(go.Scatter(x=forward.index, y=forward.values, name='Implied TS t-0', line=dict(color='red', width=2), opacity=.5, mode='lines+markers'))
fig.add_trace(go.Scatter(x=forward_week_ago.index, y=forward_week_ago.values, name='Implied TS t-7', fill='tonexty', line=dict(color='gray', width=2), opacity=.5, mode='lines+markers'))


# Adding the bracket traces
x_start = forward_week_ago.index[-1]
x_end = forward.index[-1]
y_start = min(forward_week_ago.values[-1], forward.values[-1])
y_end = max(forward_week_ago.values[-1], forward.values[-1])

# Horizontal lines
fig.add_trace(
    go.Scatter(
        x=[x_start, x_end],
        y=[y_start, y_start],
        mode="lines",
        line=dict(color="lightgray", width=1),
        showlegend=False
    )
)
fig.add_trace(
    go.Scatter(
        x=[x_start, x_end],
        y=[y_end, y_end],
        mode="lines",
        line=dict(color="lightgray", width=1),
        showlegend=False
    )
)

# Vertical line
fig.add_trace(
    go.Scatter(
        x=[x_end, x_end],
        y=[y_start, y_end],
        mode="lines",
        line=dict(color="lightgray", width=1),
        showlegend=False
    )
)


# Calculate the difference between the last points
difference = (forward.values[-1] - forward_week_ago.values[-1])*100

# Add the difference value as an annotation
annotation_trace = go.Scatter(
    x=[forward.index[-1]],
    y=[(forward.values[-1] + forward_week_ago.values[-1]) / 2],
    mode='text',
    text=[f'difference last week: {difference:.2f} bps'],
    textposition='middle left',
    textfont=dict(size=12),
    showlegend=False,
    hoverinfo='none',
    visible=True  
)

# Add the annotation trace to the figure
fig.add_trace(annotation_trace)

# Create two lists that hold the visibility status of each trace
trace_visibility = ['legendonly'] * len(df['Ticker'].unique()) + [True]*(len(fig.data) - len(df['Ticker'].unique()) - 1) + [True, False]


fig.update_layout(
    updatemenus=[
        dict(
            type="buttons",
            direction="left",
            active=0,
            x=1.0,  
            y=1.12,  
            pad={"r": 10, "t": 10},  
            showactive=False,
            buttons=list([
                dict(label="hide difference",
                     method="update",
                     args=[{"visible": trace_visibility[:-4] + [False, False, False, False, False]},  # Hide the last five traces (annotation and bracket)
                           ]),
                dict(label="show difference ",
                     method="update",
                     args=[{"visible": trace_visibility[:-4] + [True, True, True, True, True]},  # Show all traces including the annotation and the bracket
                           ]),
            ])
        )]
)


fig.show()


