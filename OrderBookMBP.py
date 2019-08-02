#|-----------------------------------------------------------------------------
#|            This source code is provided under the Apache 2.0 license      --
#|  and is provided AS IS with no warranty or guarantee of fit for purpose.  --
#|           Copyright Refinitiv 2019. All rights reserved.            --
#|-----------------------------------------------------------------------------


#!/usr/bin/env python
""" GUI example displaying Market By Price JSON data using Websockets """

import sys
import time
import socket
import json
import websocket
import base64
import queue
import tkinter as tk
from tkinter import ttk
import threading

# Global Default Variables

# Market Data related
hostName = 'myADS'    # Server name
port = '15000'        # Server Port for Websocket Connection
user = 'umer.nalla'  # DACS ID
appID = '256'       # DACS application ID (ask your Market Data team)
position = socket.gethostbyname(socket.gethostname())
ric = "VOD.L"        # RIC to subcribe to

# tkinter gui related
root = None   #Top level Widget
closing = False  # Is the GUI closing ?

# Orderbook Treeview related
obView = None  #Treeview for OrderBook
obCols = None   #Treeview Columns
sortCol = 'LV_TIM_MS'  # Sort on Orderbook entry Time
sortReverse = True     # Most recent entry at the top
obDepth = None  # Number of items / depth of Order Book
selections = []

# Summary Treeview related
summCols = ( 'DSPLY_NAME', 'CURRENCY', 'TIMACT_MS', 'SEQNUM', 'RDN_EXCHD2')  # Summary Columns to display
summFields = {}  # Store latest Summary Fields received from server
summView = None  # Treeview for Summary Fields

# Queue for communicating between Tkinter and Websocket threads
entryQ = None

# Display update related
obComplete = False   # Have we received the Complete MBP Order Book ?
obUpdated = False    # Anything changed in the MBP OB?

# Websocket related
webSocketApp = None    # Main Websocket interface 
webSocketOpen = False  # Has the Websocket connection been made?

# Has user clicked the Close button?
def on_closing():
    global closing
    closing=True

# Sort display affter items added / obUpdated or deleted.
def sort_treeview():
    obEntries = [(obView.set(child, sortCol), child)
                                for child in obView.get_children('')]
    try:
        obEntries.sort(key=lambda t: int(t[0]), reverse=sortReverse)
    except:
        obEntries.sort(reverse=sortReverse)
    for index, (val, child) in enumerate(obEntries):
        obView.move(child, '', index)

# Sort display if user clicks Column
def treeview_sort_column_click(tv, col, reverse):
    global sortCol, sortReverse
    l = [(tv.set(k, col), k) for k in tv.get_children('')]
    l.sort(reverse=reverse)
    # rearrange items in sorted positions
    for index, (val, k) in enumerate(l):
        tv.move(k, '', index)
    # reverse sort next time
    tv.heading(col, command=lambda _col=col: treeview_sort_column_click(tv, _col, not reverse))
    sortCol = col
    sortReverse = reverse

# Add entry to orderbook display - called when we receive an Add action in the MBP Map
def add_entry(k, v):
    global obView
    try:
        obView.insert("", "end", iid=k, values=(
                k, v['ORDER_PRC'], v['ORDER_SIDE'], v['ACC_SIZE'],
                    v['NO_ORD'], v['LV_TIM_MS']))
        selections.append(k)
    except:
        print("Oops", sys.exc_info())

# Update existing entry in orderbook display - called when we receive an Update action in the MBP Map
def upd_entry(k, v):
    global obView
    try:
        obView.item(k, values=(k, v['ORDER_PRC'], v['ORDER_SIDE'], v['ACC_SIZE'],
                                   v['NO_ORD'], v['LV_TIM_MS']))
        selections.append(k)
    except:
        print("Oops", sys.exc_info())

# Delete existing entry from orderbook display - called when we receive a Delete action in the MBP Map
def del_entry(k):
    global obView
    try:
        obView.delete(k)
    except:
        print("Oops", sys.exc_info())

# Check if the Summary Treeview needs updating
def upd_summary():

    global summFields
    if summFields:      # Any Summary field values been updated?
        for sCol in summCols:   # Iterate through list of summary columns we are displaying
            if sCol in summFields:  # If any of the fields we are displaying are in the update list
                summView.set("row0", sCol, summFields[sCol])    # Update the GUI with the new field value

        summFields.clear()  # Clear out the most recent field updates

# We have received a message from the server so lets parse it and act
def process_message(ws, message_json):
    """ Parse at high level and output JSON of message """
    message_type = message_json['Type']

    if message_type == "Refresh":
        if 'Domain' in message_json:
            message_domain = message_json['Domain']
            if message_domain == "Login":
                process_login_response(ws, message_json)
            elif message_domain == "MarketByPrice":
                process_mbp_response(message_json, True)

    if message_type == "Update":
        process_mbp_response(message_json, False)
    elif message_type == "Ping":
        pong_json = { 'Type':'Pong' }
        ws.send(json.dumps(pong_json))
        print("SENT:")
        print(json.dumps(pong_json, sort_keys=True, indent=2, separators=(',', ':')))

# Queue for passing events from Websocket thread to Tkinter (main app) thread
def process_queue():

    upd_summary()   # Update the Summary fields

    selections.clear()

    while (not entryQ.empty()):
        entry = entryQ.get()     # Get the top item from the queue
        binkey = entry["Key"]    # Get binary Key for item
        action = entry["Action"] # Adding / updating or deleting item with this Key value?
        keystr = base64.b64decode(binkey).decode('ascii') # convert key to readable string  (Order Price + Order Side)
        
        if (action!="Delete"):  # If we are not deleting then we must adding or updating with Field values
            fields = entry["Fields"]  # Get Fields + values for MBP entry
            if (action=="Add"):
                add_entry(keystr,fields)
            else:
                upd_entry(keystr,fields)
        else:
            del_entry(keystr)   # Delete existing entry with Key - so no Field values.

    try:
        obView.selection_set(selections)
    except:
        pass

    item_count = len(obView.get_children())    # After updating get the total item count
    obDepth.set("Depth : " + str(item_count))  # so we can update GUI
    
    if (sortCol is not None):   # If we have a sort order, sort the treeview
        sort_treeview()
    

# Process the MarketByPrice response JSON data
def process_mbp_response(mbp_json, refresh):
    """ decode orderbook response """
    global obComplete, obUpdated, summFields
    
    
    # A MBP JSON payload should contain a Map with our orderbook entries
    if "Map" in mbp_json:
        for entry in mbp_json["Map"]["Entries"]:
            entryQ.put(entry)
        
        # The Map should contain a Summary Fields section
        if "Summary" in mbp_json['Map']:
            summFields = mbp_json['Map']['Summary']['Fields']

    if (refresh):
        # If a Refresh then check to see if we have received final Refresh (large orderbook are split into multi parts)
        if "Complete" in mbp_json:
            obComplete = mbp_json["Complete"] # if present then most likely false
        else:
            obComplete = True  # Complete defaults to True, if absent then it must be True
        
        if obComplete:
            print("Final Refresh - Orderbook Complete")
        else:
            print("Multipart Refresh, not yet Complete")

    else:
        obUpdated = True


# Process the Login response from the server
def process_login_response(ws, message_json):
    """ Send item request """
    send_market_by_price_request(ws)

# Send a request for a MarketByPrice RIC to the server
def send_market_by_price_request(ws):
    """ Create and send simple Market By Price request """
    mp_req_json = {
        'ID': 2,
        'Domain' : 'MarketByPrice',
        'Key': {
            'Name': ric,
        },
    }
    ws.send(json.dumps(mp_req_json))
    print("SENT:")
    print(json.dumps(mp_req_json, sort_keys=True, indent=2, separators=(',', ':')))


# Send the Login request to the server
def send_login_request(ws):
    """ Generate a login request from command line data (or defaults) and send """
    login_json = {
        'ID': 1,
        'Domain': 'Login',
        'Key': {
            'Name': '',
            'Elements': {
                'ApplicationId': '',
                'Position': ''
            }
        }
    }

    login_json['Key']['Name'] = user
    login_json['Key']['Elements']['ApplicationId'] = appID
    login_json['Key']['Elements']['Position'] = position

    ws.send(json.dumps(login_json))
    print("SENT:")
    print(json.dumps(login_json, sort_keys=True, indent=2, separators=(',', ':')))


# Process JSON message(s) received from the server
def on_message(ws, message):
    """ Called when message received, parse message into JSON for processing """
    message_json = json.loads(message)

    # Server may pack multiple JSON data messages into single response
    for singleMsg in message_json:
        process_message(ws, singleMsg)


def on_error(ws, error):
    """ Called when websocket error has occurred """
    print(error)


def on_close(ws):
    """ Called when websocket is closed """
    global webSocketOpen
    print("WebSocket Closed")
    webSocketOpen = False


def on_open(ws):
    """ Called when handshake is Complete and websocket is open, send login """

    print("WebSocket successfully connected!")
    global webSocketOpen
    webSocketOpen = True
    send_login_request(ws)

# Init our GUI - the Summary TreeView and the Orderbook TreeView etc
def init_ob_gui():

    global root, summView, obCols, obView, obDepth

    root = tk.Tk() 
    root.protocol("WM_DELETE_WINDOW", on_closing)
    tk.Label(root, text="MBP Order Book : "+ric, font=("Arial",20)).pack(fill=tk.X)

    # Set summary colums
    summFrame = tk.Frame(root)
    summFrame.pack(fill=tk.X)
    summView = ttk.Treeview(summFrame, columns=summCols, show='headings', height=1)
    for sumcol in summCols:
        summView.heading(sumcol, text=sumcol,anchor=tk.W)
        summView.column(sumcol, width=120, stretch=True)
    summView.pack(fill=tk.X)
    summView.insert("", "end", iid="row0", values=('', '', '', 0, ''))

    # Create OrderBook TreeView
    obCols = ('Key', 'ORDER_PRC', 'ORDER_SIDE', 'ACC_SIZE', 'NO_ORD', 'LV_TIM_MS')
    obFrame = tk.Frame(root)
    obFrame.pack(fill=tk.X)
    obView = ttk.Treeview(obFrame, columns=obCols, show='headings', height=30)
    obScroll = ttk.Scrollbar( obFrame, orient='vertical', command=obView.yview)
    obScroll.pack(fill=tk.Y, side=tk.RIGHT)
    obView.configure(yscrollcommand=obScroll.set)
    obDepth = tk.StringVar()
    # Set OB Treeview column headings
    for col in obCols:
        obView.heading(col, text=col,command=lambda _col=col: treeview_sort_column_click(obView, _col, False))    
        obView.column(col, anchor='center', width=100)    
    obView.pack(fill=tk.X)
    tk.Label(root, textvariable=obDepth, font=("Arial",15)).pack(fill=tk.X)

    root.lift()
    root.update_idletasks()
    root.update()



if __name__ == "__main__":

    # Initialise the Tkinter gui components
    init_ob_gui()

    # Queue for passing data from Websocket thread to main app / gui thread
    entryQ = queue.Queue(maxsize=0)
    
    # Start websocket handshake
    ws_address = "ws://{}:{}/WebSocket".format(hostName, port)
    print("Connecting to WebSocket " + ws_address + " ...")
    webSocketApp = websocket.WebSocketApp(ws_address, header=['User-Agent: Python'],
                                        on_message=on_message,
                                        on_error=on_error,
                                        on_close=on_close,
                                        subprotocols=['tr_json2'])
    webSocketApp.on_open = on_open

    # Websocket thread
    wst = threading.Thread(target=webSocketApp.run_forever)
    wst.start()

    
    try:
        # Wait till we receive complete Orderbook
        while (not obComplete):
            # We receive Summary fields in first Refresh - so display them once available
            if summFields:
                upd_summary()
            time.sleep(0.1);

        # Complete Orderbook received - so display in GUI
        process_queue()
        root.update_idletasks()
        root.update()

        # deselect rows after 3 seconds
        desel_time = time.time() + 3

        # Loop until GUI closed down by user
        while not closing:
            # If we have recevied any updates, display them in GUI
            if (obUpdated):
                obUpdated=False
                process_queue()
                desel_time = time.time() + 3
            else:
                # deselect any selected rows after 3 seconds
                if (time.time() >= desel_time):
                    selections.clear()
                    obView.selection_set(selections)
            # Process GUI events etc
            root.update_idletasks()
            root.update()
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        root.destroy()
        webSocketApp.close()
