# Article.WebsocketAPI.Python.OrderBook
GUI Python example which Consumes Orderbook data using Elektron Websocket API

## Consuming Order Book data with Elektron Websocket API

***Prerequisite** - Must have worked through the existing <a href="https://developers.refinitiv.com/elektron/websocket-api/learning" target="_blank">Elektron Websocket API Tutorials</a> and be confident in requesting and processing MarketPrice data*

If you have explored the Elektron Websocket API examples we provide, you will have noted that they are almost exclusively related to MarketPrice data - often referred to as Level 1 data.

However, the Websocket API can be used to request much richer real-time content including (*but not limited to*) the following types of Level 2 data: 


| Type            | Also known as                      | Description                              |
|-----------------|------------------------------------|------------------------------------------|
| Market-By-Price | Market Depth Aggregated Order Book | Collection of orders for an instrument grouped by Price point i.e. multiple orders per ‘row’ of data |
| Market-By-Order | Detailed Order Book                | Unique orders i.e. each ‘row’ represents a single order |
| Market Maker    | Market Participants                | Market maker content where quotes from a single market maker reside within a single ‘row’ |


On the face of it, requesting Level 2 data is not much different from requesting Level 1 MarketPrice data.

### Requesting Level 2 Data  

So, for example to request MarketPrice data for Vodafone from LSE, we send the following JSON request to the server:

```json
"ID":2,
  "Key":{
    "Name":"VOD.L"
  }
```
Whereas, if we want to request say Market-By-Price or Market-By-Order data we would send the following:

```json
{
  "ID":2,
  "Key":{
    "Name":"VOD.L"
  },
  "Domain":"MarketByPrice"
}
```

```json
{
  "ID":2,
  "Key":{
    "Name":"VOD.L"
  },
  "Domain":"MarketByOrder"
}
```

As you can see, the only difference is that we have added the '*Domain*' attribute and set its value to '*MarketByPrice*' or '*MarketByOrder*' - pretty straightforward.  


### Processing Level 2 Data Response  

Whilst, the request mechanism was straightforward, processing the response is where it gets a bit more interesting....

When we make a MarketPrice request, the response payload is flat - consisting of  field + value pairs e.g.

```json
"Fields":{
      "52WK_HIGH":214.6,
      "52WK_LOW":133.48,
...
...
      "ASK":139.08,
      "ASKSIZE":5305,
      "ASK_TIM_MS":44808257,
      "ASK_TIM_NS":"12:26:48.257",
      "BID":139.02,        
...
...
      "YRLOW":133.48,
      "YRLO_IND":"15M.Yr.L"
    },
```

However, due to the richer deeper nature of Level 2 data, we cannot easily deliver Level 2 data in the same flat format. We use nested / hierarchical data structures so that we can more efficiently transmit this richer content and also make it easier for the consumer to process.   

For example, a MarketByPrice (MBP) response - a Market Depth Aggregated Order book where market orders are grouped by price point and order side (Bid or Ask) - could easily contain several hundred price points.   
As trading takes place, the changes to the data can be quite volatile - as price points are added & removed or the number of orders / order sizes for each price point rise & fall.  

As the order book entries are grouped by price point and order side, we use an associative array i.e. Map (C++/Java) / Dict (Python) where the key is a combination of price + side and the value is a list of fields that represents that entry in the order book e.g.

```json
"200A": {"ORDER_PRC": 200.0, "ORDER_SIDE": "ASK", "ACC_SIZE": 10272, "NO_ORD": 2, "LV_TIM_MS": 56123427} ,
"131B": {"ORDER_PRC": 131.0, "ORDER_SIDE": "BID", "ACC_SIZE": 51700, "NO_ORD": 3, "LV_TIM_MS": 56123421} ,
"134.84A": {"ORDER_PRC": 134.84, "ORDER_SIDE": "ASK", "ACC_SIZE": 87188, "NO_ORD": 1, "LV_TIM_MS": 55814497} ,
"129B": {"ORDER_PRC": 129.0, "ORDER_SIDE": "BID", "ACC_SIZE": 2000, "NO_ORD": 1, "LV_TIM_MS": 56400171} ,
```

In the above example we have some Market-By-Price entries with e.g. 
* key value of '200A' for 2 Ask orders with a price point of '200.0'
* key value of '131B' for 3 Bid orders with a price point of 131.01 
* and so on...

Using the Associative array takes care of how to represent the various price points + order type in the order book - but we need something more in order to transmit the changes to the order book from the server to the consumer. We need to advise the consumer when:
* a new entry i.e. price point + side is added to the order book
* existing entry is updated e.g. the number of orders or accumulated size of orders (for an existing price point + side) changes
* existing entry is deleted when all orders at that price point + side are filled

To address the above requirement, we use an Action attribute to advise the consumer on how to process each entry in the payload e.g.
```json
        {
          "Action": "Add",
          "Key": "MTI4LjU2QQ==",
          "Fields": {
            "ORDER_PRC": 128.56,
            "ORDER_SIDE": "ASK",
            "ACC_SIZE": 26592,
            "NO_ORD": 7,
            "LV_TIM_MS": 52674138
          }
        },
...
...
        {
          "Action": "Update",
          "Key": "MTI4LjUyQQ==",
          "Fields": {
            "ORDER_PRC": 128.52,
            "ORDER_SIDE": "ASK",
            "ACC_SIZE": 27521,
            "NO_ORD": 7,
            "LV_TIM_MS": 52690107
          },
...
...
        {
          "Action": "Delete",
          "Key": "MTI4LjRB=="
        }
```

In the above snippets from a payload, we can see the server is telling the consumer that a new entry was added to the order book, an existing one was updated and an existing one was deleted. 

A few things to note here:
* The Key is '*base64*' encoded and that is why it does not look like the '200A', '131B' examples I used earlier - more on this later.
* Whilst the 'Add' and 'Update' action type entries contain Fields with Values - the 'Delete' entry only contains a Key - which makes sense as we don't need field values if we are deleting an entry

### Summary Data

In addition to the Order book entries, the server also needs to transmit some additional values / properties which apply to the whole order book rather than individual entries. Examples of these values can include things like:
* Instrument name
* Currency of the prices
* Exchange ID
* Trading Status
and so on...

```json
"Summary": {
        "Fields": {
          "PROD_PERM": 249,
          "DSPLY_NAME": "VODAFONE GROUP",
          "CURRENCY": "GBp",
          "ACTIV_DATE": "2019-07-22",
          "LOT_SIZE_A": 1,
          "RECORDTYPE": 113,
          "SEQNUM": 3838578,
          "RDN_EXCHD2": "LSE",
...
...
          "TRD_STATUS": "N ",
          "HALT_RSN": "NH",
          "PERIOD_CD2": "T",
          "INST_PHASE": "T  ",
          "OR_PRC_BAS": "PRC",
          "ORDBK_DEPH": "FB    "
        }
      }
```

The full set of Summary data fields is transmitted with the initial Refresh message - i.e. the first message received in response to a successful request. After which, a partial field list will be sent within an Update message, by the server as and when any of the field values change.

### Multipart Refresh Message

As explained in the basic <a href="https://developers.refinitiv.com/elektron/websocket-api/learning?content=63571&type=learning_material_item" target="_blank">Level 2 Market Depth Data</a> tutorial - the server can split the Level 2 data Refresh message into multiple Refresh messages - for instruments with deep order books.  

```json
{
  "ID": 2,
  "Type": "Refresh",
  "Domain": "MarketByPrice",
  "Key": {
    "Service": "ELEKTRON_DD",
    "Name": "VOD.L"
  },
  "State": {
    "Stream": "Open",
    "Data": "Ok",
    "Text": "All is well"
  },
  "Complete": false,
  "SeqNumber": 32480,
  "Map": {
    "KeyType": "Buffer",
    "Summary": {
      "Fields": {
        "PROD_PERM": 249,
        "DSPLY_NAME": "VODAFONE GROUP",
        "CURRENCY": "GBp",
        "ACTIV_DATE": "2019-07-22",
        "LOT_SIZE_A": 1,
...
...
        "ORDBK_DEPH": "FB    "
      }
    },
    "CountHint": 276,
    "Entries": [
      {
        "Action": "Add",
        "Key": "MTI3LjQ0Qg==",
        "Fields": {
          "ORDER_PRC": 127.44,
          "ORDER_SIDE": "BID",
          "ACC_SIZE": 5586,
          "NO_ORD": 1,
          "LV_TIM_MS": 50419848
        }
      },
      {
        "Action": "Add",
        "Key": "MTI5LjQ2QQ==",
        "Fields": {
          "ORDER_PRC": 129.46,
          "ORDER_SIDE": "ASK",
          "NO_ORD": 1,
          "ACC_SIZE": 4713,
          "LV_TIM_MS": 50452301
        }
      },
...
...
      {
        "Action": "Add",
        "Key": "MTI1LjU2Qg==",
        "Fields": {
          "ORDER_PRC": 125.56,
          "ORDER_SIDE": "BID",
          "NO_ORD": 1,
          "ACC_SIZE": 100000,
          "LV_TIM_MS": 50153370
        }
      }
    ]
  }
}
...
...
{
  "ID": 2,
  "Type": "Refresh",
  "Domain": "MarketByPrice",
  "Key": {
    "Service": "ELEKTRON_DD",
    "Name": "VOD.L"
  },
  "State": {
    "Stream": "Open",
    "Data": "Ok",
    "Text": "All is well"
  },
  "SeqNumber": 32480,
  "Map": {
    "KeyType": "Buffer",
    "Entries": [
      {
      "Action": "Add",
      "Key": "MTI4Ljg2QQ==",
      "Fields": {
        "ORDER_PRC": 128.86,
        "ORDER_SIDE": "ASK",
        "NO_ORD": 1,
        "ACC_SIZE": 5737,
        "LV_TIM_MS": 52763634
      }
    },
...
...
      {
        "Action": "Add",
        "Key": "MTIzQg==",
        "Fields": {
          "ORDER_PRC": 123,
          "ORDER_SIDE": "BID",
          "NO_ORD": 6,
          "ACC_SIZE": 53602,
          "LV_TIM_MS": 39748719
        }
      }
    ]
  }
}
```
Note that the first Refresh Message has an attribute '***Complete : false***', but the final Refresh does not.  
With Multi-part Refresh messages, all but the final Refresh Messages have an attribute of Complete: false.  The final Refresh does not have this attribute as the default value for Complete is true.

So, we need to wait till we receive a Refresh message ***without*** the Complete attribute in order to mark the initial Order Book delivery complete.  


## GUI Example

The other thing you may have noted about our examples is that they are almost exclusively console applications which dump the data out.

Whilst this is acceptable for flat nature of MarketPrice data, it is harder to make sense of a hierarchical data set like an Order Book.

For this reason I decided to implement a simple GUI to make the data easier to view.

I will use the Tkinter Python GUI package - to create a very simple GUI application which displays a few of Summary data fields and the MarketByPrice (MBP) aggregated Order Book. It will display the initial values for both items and continue to update the display to reflect the changes to the data.

Ideally I would have liked to update the display in real-time - as and when I receive data. However, it appears that the Tkinter GUI can only updated from a single thread. The Websocket client I intend to use runs in its own thread with asynchronous callbacks.   

Therefore, in order to keep things simple and not distract from the objective of this article, I will use a Queue to communicate between the Tkinter (main thread) and the Websocket thread.


## Code Snippets

The objective of this article is to illustrate how to Consume and Process Level 2 data - focusing on MarketByPrice domain - therefore the code snippets I will present will mostly focus on this aspect. I will not be focusing on the Tkinter aspect - especially since this is the first time I have used Tkinter and no doubt there are better / more efficient means of implementing the GUI.

As per the prerequisites you should have worked through the basic tutorials and be familiar with the steps required to establish a Websocket connection, authentication, login and requesting MarketPrice data.

So, I skip forward to the point of making a MBP request

## MarketByPrice Request

I will form the JSON for a MBP request of Vodafone from the LSE and send the request over the Websocket connection to the server

```python
def send_market_by_price_request(ws):
    """ Create and send simple Market By Price request """
    mp_req_json = {
        'ID': 2,
        'Domain' : 'MarketByPrice',
        'Key': {
            'Name': "VOD.L",
        },
    }
    ws.send(json.dumps(mp_req_json))
```

## MarketByPrice Response

Shortly after sending a valid MBP request, the server should respond with a JSON payload containing the initial Refresh (one or more parts) which we can then process.

Ordinarily, I would extract the Summary Data and the Order book data and store both in a Python collection, so I would do something like the following:
```python
def process_mbp_response(mbp_json, refresh):
    """ decode orderbook response """
    
    if "Map" in mbp_json:
        if "Summary" in mbp_json['Map']:
            summFields = mbp_json['Map']['Summary']['Fields']
        
        # Extract Order Book entries    
        for entries in mbp_json["Map"]["Entries"]:
            binkey = entries["Key"]
            keystr = base64.b64decode(binkey).decode('ascii')
            action = entries["Action"]
            if (action!="Delete"):
                orderbook[keystr]=entries["Fields"]
            else:
                del orderbook[keystr]

```
Let us break down the above code:
1. The first thing we do is check that the payload does indeed contain a 'Map' payload as described earlier
2. Next, we check for the presence of the Summary fields and extract those into a dict
3. We then iterate through any Orderbook entries as follows
    * Extract the binary Key (which is delivered in base64 encoding as described earlier) e.g. '*MTI4LjU2QQ==*'
    * Convert the Key into string format e.g. '*128.56A*'
    * Extract the Action type for this Map entry
    * If the Action is Add or Update then just apply the entry data  to the *orderbook* dict
    * Since the Key value is unique, a new item will be added to the dict or an existing item will be replaced accordingly
    * If the Action is Delete then we remove the dict item

The above typically what you would do if you need to build an application level representation of the orderbook. However, since I am only interested in updating a GUI via a Queue my code a this point will simpler:

```python
def process_mbp_response(mbp_json, refresh):
    """ decode orderbook response """
    
    if "Map" in mbp_json:
        # Extract Summary Data fields
        if "Summary" in mbp_json['Map']:
            summFields = mbp_json['Map']['Summary']['Fields']

        # Extract Order Book entries and add to Queue
        for entry in mbp_json["Map"]["Entries"]:
            entryQ.put(entry)
```
This snippet  starts off similar to the previous snippet:
1. Check the payload contains a 'Map' payload as described earlier
2. Check for and extract the Summary fields into a dict
3. Iterate through any Orderbook entries and add them to the Queue *entryQ* for later processing

After processing the Summary Fields and Orderbook payload, we then check for the Completion attribute (or lack of) to confirm if we have received the Final Refresh 
```python

    global obComplete, obUpdated, summFields

    if (refresh):
         # If a Refresh then check to see if we have received final Refresh (orderbook can be split into multi parts)
         if "Complete" in mbp_json:
             obComplete = mbp_json["Complete"] # if present then most likely false
         else:
             obComplete = True  # Complete defaults to True, if absent then it must be True
         
         if obComplete:
             print("Final Refresh - Orderbook complete")
         else:
             print("Multipart Refresh, not yet complete")
    
     else:
         obUpdated = True
```
If we are dealing with a Refresh type message and it contains a Complete attribute, then this indicates that there are more Refresh messages to follow - otherwise we mark the Orderbook delivery as complete.
If this was not a Refresh, we set a flag to indicate an Update type message was received.

## Processing the Summary field values and Order Book entries

At this point, we would typically extract the individual Summary fields and the Orderbook entries from the dicts and process them as per your requirements.

As I am writing a GUI example, and I have already been transferring the JSON payload to the Queue, I will go ahead and process ***entryQ***.

As the Websocket processing is being performed by its own thread, we will use the main application thread to process ***entryQ*** and update the GUI.

Firstly we need to display the initial Summary Field data and the full Orderbook once it has been delivered completely. 

```python
# Wait till we receive complete Orderbook
       while (not obComplete):
           # We receive Summary fields in first Refresh - so display them when available
           if summFields:
               upd_summary()
           time.sleep(0.1);

       # Complete Orderbook received - so display in GUI
       process_queue()
       root.update_idletasks()
       root.update()
```
The Summary fields arrive in the first Refresh message so we don't need to wait for the complete Orderbook in order to display them.
Once the Orderbook is marked complete, we process the Queue and populate the main Orderbook Treeview.

### Display the Summary Fields
```python
summCols = ( 'DSPLY_NAME', 'CURRENCY', 'TIMACT_MS', 'SEQNUM', 'RDN_EXCHD2')

def upd_summary():
    global summFields

    if summFields:      # If any Summary field values have been updated
        for sCol in summCols:   # iterate through list of summary columns we are displaying
            if sCol in summFields:  # If any of the fields we are displaying are in the update list
                summView.set("row0", sCol, summFields[sCol])    # Update the GUI with the new field value
                
        summFields.clear()  # Clear out the most recent field updates
```
Whilst the initial Summary data can contain many fields (the VOD.L example contained 30 fields), I just want to display a few key ones - so I have declared a tuple with those select field names.
We then iterate through the tuple and search for there presence in the Summary fields payload we received from the server - be it the Refresh or subsequent update.
If any of the select fields are present in the payload, we reflect this in the GUI (a Tkinter Treeview created during application initialisation).   

### Process the Queue after the Final Refresh
Once the full Orderbook has been received and marked as Complete, we can process the Queue for the first time.

```python
def process_queue():

    selections.clear()

    while (not entryQ.empty()):
        entry = entryQ.get() # Get the top item from the queue
        binkey = entry["Key"]  # Get binary Key for item
        action = entry["Action"] # Adding / updating or deleting item?
        keystr = base64.b64decode(binkey).decode('ascii') # convert key to readable string
        
        if (action!="Delete"):  # If we not deleting then  must adding / updating Field values
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

```
For a bit more visual effect, we will temporarily select the items in the Treeview that we add or update, so initially - we clear down any existing selections.

We then implement something similar to the previous snippet - albeit for a Treeview rather than a dict:
1. We check the payload contains a 'Map' payload as described earlier
2. Check for the presence of & extract the Summary fields
3. Iterate through any Orderbook entries:
    * Extract the binary Key & convert it to readable format
    * Extract the Action type for each entry
    * For Add or Update actions we extract the fields
    * The Treeview is indexed on the Key column, we can Insert or update each row using the Key and passing the field values
    * For Delete action we delete the existing row using the Key
4. Once we have processed the Queue entries, we select the newly added / updated items in the Treeview

If you look at the code for **add\_entry**** you will note that the Key value is used for ***iid*** & the first column and the actual payload fields values are applied to the remaining columns e.g.
```python
obView.insert("", "end", iid=k, values=(
            k, v['ORDER_PRC'], v['ORDER_SIDE'], v['ACC_SIZE'], v['NO_ORD'], v['LV_TIM_MS']))
```
This allows us to update or delete an existing row when required by using the Key value.

## Intermittently Update the GUI

Referring to the rest of the **\__main\__** method, this enters a loop which continues to run until the user terminates the application.  
Whilst looping, if the ***obUpdated*** flag is set by the Websocket thread, we process the queue again to reflect the latest Orderbook changes received in the GUI.    
The loop also takes care of clearing down any selected rows in the Orderbook Treeview after a few seconds have elapsed (this is purely for visual effect).

# Closing Summary

I hope the above information provided a useful overview of how to process Level 2 MarketData. For a more detailed explanation of the Orderbook including MarketByOrder domain, I recommend you read the article mentioned below.
However, we can recap the main points covered above:

* Level 2 data is represented using hierarchical / nested data structures
* The JSON Payload contains common Summary Data as well as the Orderbook entries
* For a deeper Orderbook the initial payload may be split over multiple Refresh messages
* Each entry in the Orderbook payload will have a Key as well as an Action - along with field values (for Add/Update actions)



## Additional Resources

<a href="https://developers.refinitiv.com/elektron/websocket-api/learning?content=63483&type=learning_material_item" target="_blank">Websocket API tutorials</a>

<a href="https://developers.refinitiv.com/article/how-sort-process-level-2-orderbook-data-using-ema-c-api" target="_blank">How to Sort & Process Level 2 Orderbook Data</a>



