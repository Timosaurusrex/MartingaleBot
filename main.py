#Grid Trading Bot, which interacts with the binance api
#© Written by Timo Perzi and Christoph Handschuh, on 31-03-2022
print("© Written by Timo Perzi and Christoph Handschuh, on 31-03-2022, Version: 3.0")

import json
import sys
import config
import requests
import websocket
from binance import Client
from telegram.ext.updater import Updater
from telegram.update import Update
from telegram.ext.callbackcontext import CallbackContext
from telegram.ext.commandhandler import CommandHandler

updater = Updater(config.telegram_key, use_context=True)
client = Client(config.API, config.API_key)
start_capital = 825     #825/60%/15$ thr: 1.1%, mtg: 55

rsi = 0
bricks = []
run = False
with open("back_up.txt", "r") as f:  #Restore everything
    mtg = float(f.readline())
    threshold = float(f.readline())
    buy_price = float(f.readline())
    tradenum = float(f.readline())

def kill(update: Update, context: CallbackContext):
    update.message.reply_text("Code killed!!!")
    print("Program killed!")
    sys.exit()

def start(update: Update, context: CallbackContext):
    global run
    run = True
    update.message.reply_text("Code started!!!")

def stop(update: Update, context: CallbackContext):
    global run
    run = False
    update.message.reply_text("Code stopped!!!")

def on_open(ws):
    global bricks, rsi

    print('opened connection')
    bricks = requests.get('https://api.binance.com/api/v1/klines?symbol=' + config.symbol.upper() + '&interval=' + config.rsi_interval + '&limit=14').json()
    win = 0
    lose = 0
    for i in range(13):
        if float(bricks[i][4]) < float(bricks[i + 1][4]):
            win = win + (float(bricks[i + 1][4]) - float(bricks[i][4]))
        else:
            lose = lose + (float(bricks[i][4]) - float(bricks[i + 1][4]))
        if win != 0 and lose != 0:
            rsi = 100 - 100 / (1 + (win / lose))
        else:
            rsi = 50
        bricks[i] = float(bricks[i][4])

    updater.dispatcher.add_handler(CommandHandler('stop', stop))
    updater.dispatcher.add_handler(CommandHandler('start', start))
    updater.dispatcher.add_handler(CommandHandler('kill', kill))
    updater.start_polling()

def on_close(ws ,a ,b):
    print('closed connection')
    ws = websocket.WebSocketApp("wss://stream.binance.com:9443/ws/" + config.symbol.lower() + "@kline_" + config.rsi_interval, on_open=on_open, on_close=on_close, on_message=on_message, on_error=on_error)
    ws.run_forever()

def on_error(ws, error):
    print(error)

def save_back_up():
    global mtg, threshold, buy_price, tradenum
    with open(f"back_up.txt", 'w') as f:
        f.write(f"{str(mtg)}\n{str(threshold)}\n{str(buy_price)}\n{str(tradenum)}")

def Quantity(price):
    global start_capital, mtg
    return ((start_capital/mtg) * 1.01) / price

def on_message(ws, msg):
    global rsi, bricks, tradenum, buy_price

    msg_json = json.loads(msg)
    price = float(msg_json['k']['c'])
    if msg_json['k']['x']:  #If Candle closed
        bricks.append(price)
        if len(bricks) == 13:
            win = 0
            lose = 0
            bricks.pop(0)
            for i in range(12):
                if bricks[i] < bricks[i + 1]:
                    win = win + (bricks[i + 1] - bricks[i])
                else:
                    lose = lose + (bricks[i] - bricks[i + 1])
                if win != 0 and lose != 0:
                    rsi = 100 - 100 / (1 + (win / lose))
                else:
                    rsi = 50

    if run == False:
        print(f"run: {run}")

    if run:
        if tradenum == 0:
            print("RSI: " + str(rsi))

        if tradenum == 0 and rsi < config.rsi_threshold:
            client.order_market_buy(symbol=config.symbol.upper(), quantity=Quantity(price))
            with open("history.txt", "a") as f:
                f.write("Buy" + str(price).replace(".", ","))
            tradenum = 1
            buy_price = price
            client.order_limit_sell(symbol=config.symbol.upper(), quantity=Quantity((buy_price + ((buy_price / 100) * threshold))), price=(buy_price + ((buy_price / 100) * threshold)))
            client.order_limit_buy(symbol=config.symbol.upper(), quantity=Quantity((buy_price - ((buy_price / 100) * threshold))), price=(buy_price - ((buy_price / 100) * threshold)))
            save_back_up()

        elif (tradenum < mtg and len(client.get_open_orders(symbol=config.symbol.upper())) < 2) or (
                tradenum == mtg and len(client.get_open_orders(symbol=config.symbol.upper())) < 1):
            if client.get_open_orders(symbol=config.symbol.upper()) == "SELL" and tradenum != mtg:  # Bought
                tradenum += 1
                with open("history.txt", "a") as f:
                    f.write("Buy" + str(price).replace(".", ","))
            elif client.get_open_orders(symbol=config.symbol.upper()) == "BUY" or (tradenum == mtg and len(client.get_open_orders(symbol=config.symbol.upper())) == 0):  # Sold
                tradenum -= 1
                with open("history.txt", "a") as f:
                    f.write("Sell" + str(price).replace(".", ","))

            for i in range(len(client.get_open_orders(symbol=config.symbol.upper()))):  # Cancel Orders
                client.cancel_order(orderId=client.get_open_orders(symbol=config.symbol.upper())[i]["orderId"])

            if tradenum >= 0:
                client.order_limit_buy(symbol=config.symbol.upper(), quantity=Quantity((buy_price - ((buy_price / 100) * tradenum * threshold))), price=(buy_price - ((buy_price / 100) * tradenum * threshold)))
                client.order_limit_sell(symbol=config.symbol.upper(), quantity=Quantity((buy_price - ((buy_price / 100) * (tradenum - 2) * threshold))), price=(buy_price - ((buy_price / 100) * (tradenum - 1) * threshold)))
            elif tradenum == mtg:
                client.order_limit_sell(symbol=config.symbol.upper(), quantity=Quantity((buy_price - ((buy_price / 100) * (tradenum - 2) * threshold))), price=(buy_price - ((buy_price / 100) * (tradenum - 1) * threshold)))
            save_back_up()

ws = websocket.WebSocketApp("wss://stream.binance.com:9443/ws/" + config.symbol.lower() + "@kline_" + config.rsi_interval, on_open=on_open, on_close=on_close, on_message=on_message, on_error=on_error)
ws.run_forever()
