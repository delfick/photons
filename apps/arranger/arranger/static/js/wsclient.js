import {
  call,
  all,
  cancel,
  fork,
  put,
  race,
  spawn,
  take,
  delay
} from "redux-saga/effects";
import { createAction, createReducer } from "redux-act";
import { END, channel } from "redux-saga";
import { v4 as uuidv4 } from "uuid";

class WSStateKls {
  Loading = createAction("Starting to open connection");
  Error = createAction("Got an error connecting to the websocket");
  Connected = createAction("Successfully connected to the websocket");
  ServerTime = createAction("Got a new server time from the server", time => ({
    time
  }));

  disabledSelector(state) {
    return state.ws.loading || state.ws.error;
  }

  reducer() {
    return createReducer(
      {
        [this.Loading]: (state, payload) => {
          return { ...state, loading: true };
        },
        [this.Error]: (state, { error }) => {
          let errorStr = "Unknown error";
          try {
            errorStr = `${error.error_code}: ${error.error}`;
          } catch (e) {
            try {
              errorStr = JSON.stringify(error);
            } catch (e) {
              try {
                errorStr = error.toString();
              } catch (e) {
                errorStr = String(error);
              }
            }
          }

          return { ...state, error, errorStr, loading: true };
        },
        [this.Connected]: (state, payload) => {
          return {
            ...state,
            error: undefined,
            errorStr: undefined,
            loading: false
          };
        }
      },
      {
        error: undefined,
        errorStr: undefined,
        devices: {},
        loading: true
      }
    );
  }
}

export const WSState = new WSStateKls();

export const WSCommand = createAction(
  "Command to the websocket server",
  (
    path,
    body,
    { onreply, onerror, onprogress, timeout, original, parentMessageIds }
  ) => ({
    path,
    body,
    onreply,
    onerror,
    onprogress,
    timeout,
    original,
    parentMessageIds
  })
);

function* maybeTimeoutMessage(actions, messageId) {
  var action = actions[messageId];
  yield delay(action.timeout || 5000);
  try {
    var response = action.onerror({
      error: "Timedout waiting for a reply to the message",
      error_code: "Timedout"
    });
  } finally {
    if (response) {
      // finally block to make sure the response we made is sent if we get cancelled
      yield put(response);
      delete actions[messageId];
    }
  }
}

function* sendToSocket(socket, sendch, actions) {
  while (true) {
    var action = yield take(sendch);
    if (socket.readyState === 1) {
      socket.send(JSON.stringify(action.data));
    } else {
      try {
        var response = action.onerror({
          error: "Connection to the server wasn't active",
          error_code: "InactiveConnection"
        });
      } finally {
        // We use a finally block to make sure the response is dispatched
        // if this saga gets cancelled
        if (response) {
          yield put(response);
          delete actions[action.messageId];
        }
      }
    }
  }
}

function* tickMessages(socket) {
  while (true) {
    yield delay(15000);
    if (socket.readyState === 1) {
      socket.send(JSON.stringify({ path: "__tick__" }));
    }
  }
}

function* startWS(url, count, sendch, receivech, actions) {
  var socket = new WebSocket(url);

  var onerrors = [];
  var oncloses = [];

  var ws = new Promise((resolve, reject) => {
    socket.onopen = () => {
      resolve(socket);
    };

    socket.onmessage = event => receivech.put(event);

    socket.onerror = evt => {
      console.error("Websocket got error", evt);
      reject(evt);
    };

    socket.onclose = evt => {
      console.error("Websocket closed", evt);
      reject(evt);
      oncloses.map(cb => {
        try {
          cb(evt);
        } catch (e) {
          console.error(e);
        }
      });
    };
  });

  var start = Date.now();

  try {
    var { timeout, w } = yield race({ timeout: delay(2000), w: ws });
  } catch (e) {
    console.error("Failed to start websocket connection", e);
    yield put(
      WSState.Error({
        error: {
          error: "Could not connect to server",
          error_code: "FailedToConnected"
        }
      })
    );
    var diff = Date.now() - start;
    if (diff < 1000) {
      yield delay(1000 - diff);
    }
    return;
  }

  if (timeout) {
    console.error("timed out waiting for websocket");
    socket.close();
    return false;
  }

  var waiter = yield call(channel);
  var ticker = yield fork(tickMessages, w);
  var sender = yield fork(sendToSocket, w, sendch, actions);

  oncloses.push(() => {
    waiter.put(END);
  });

  try {
    yield put(WSState.Connected());
    yield take(waiter);
  } finally {
    yield put(
      WSState.Error({
        error: { error: "Server went away", error_code: "ServerWentAway" }
      })
    );
    waiter.close();
    yield cancel(ticker);
    yield cancel(sender);
  }
}

function* processWsSend(commandch, sendch, actions, defaultonerror) {
  var normalise = (
    messageId,
    { path, body, onerror, onreply, onprogress, original, timeout }
  ) => {
    var done = false;

    var create = (cb, msg) => {
      try {
        return cb(msg);
      } catch (e) {
        console.error(e);
        try {
          return defaultonerror({
            error_code: "INTERNAL_ERROR",
            error: e.toString()
          });
        } catch (e2) {
          console.error(e2);
        }
      }
    };

    var data = { path, body, message_id: messageId };
    var doerror = error => {
      if (done) {
        return;
      }

      done = true;
      if (onerror) {
        return put(create(onerror, { ...error, messageId, original }));
      }
    };

    var doreply = (data, msgid) => {
      if (done || !data) {
        return;
      }

      done = true;
      let payloads = [];

      if (data.error_code && onerror) {
        payloads.push(
          put(
            create(onerror, {
              ...data,
              namespace: "",
              messageId,
              original
            })
          )
        );
      } else if (data.error && onerror) {
        payloads.push(
          put(
            create(onerror, {
              ...data.error.msg,
              namespace: data.error.namespace,
              messageId,
              original
            })
          )
        );
      }

      if (data.result && onreply) {
        payloads.push(
          put(create(onreply, { messageId, data: data.result, original }))
        );
      }

      return all(payloads);
    };

    var doprogress = progress => {
      if (onprogress) {
        return put(create(onprogress, { messageId, progress, original }));
      }
    };

    return {
      data,
      messageId,
      timeout: timeout,
      onreply: doreply,
      onerror: doerror,
      onprogress: doprogress
    };
  };

  while (true) {
    var { payload } = yield take(commandch);
    let messageId = uuidv4();
    if (payload.parentMessageIds) {
      messageId = [...payload.parentMessageIds, messageId];
    }
    var normalised = normalise(messageId, payload);
    actions[messageId] = normalised;
    normalised.timeouter = yield spawn(maybeTimeoutMessage, actions, messageId);
    yield put(sendch, normalised);
  }
}

function* processWsReceive(receivech, actions) {
  var makeResponse = (action, data) => {
    if (data.reply) {
      if (data.reply.progress) {
        return action.onprogress(data.reply.progress);
      } else {
        return action.onreply(data.reply, data.message_id);
      }
    }

    if (data.error) {
      return action.onerror(data.error);
    }
  };

  while (true) {
    var { data } = yield take(receivech);
    try {
      data = JSON.parse(data);
    } catch (e) {
      console.error("failed to parse json from the server", e);
      continue;
    }

    if (!data.message_id) {
      console.error("Got a message from the server without a message id", data);
      continue;
    }

    if (data.message_id == "__tick__") {
      continue;
    }

    if (data.message_id == "__server_time__") {
      yield put(WSState.ServerTime(data.reply));
      continue;
    }

    var action = actions[data.message_id];

    if (!action) {
      console.error(
        "Got a message from the server with unknown message id",
        data.message_id,
        data
      );
      continue;
    }

    if (action.timeouter) {
      yield cancel(action.timeouter);
    }

    let response = undefined;
    try {
      response = makeResponse(action, data);
    } finally {
      // Really make sure we put our response
      // This is because once the response is made,
      // no other response can be made
      if (response) {
        yield response;
      }
    }

    // Finished with this message if not a progress message
    if (response && (!data.reply || !data.reply.progress)) {
      delete actions[data.message_id];
    }
  }
}

export function* getWSCommands(commandch) {
  while (true) {
    var nxt = yield take(WSCommand);
    yield put(commandch, nxt);
  }
}

export function* listen(url, defaultonerror, delayMS) {
  var count = 0;
  var messages = {};
  var sendch = yield call(channel);
  var receivech = yield call(channel);
  var commandch = yield call(channel);

  if (defaultonerror === undefined) {
    defaultonerror = e => console.error(e);
  }

  // This is outside the while true so that we don't miss messages
  // when the server goes away and before we've started processWsSend again
  yield fork(getWSCommands, commandch);

  while (true) {
    yield put(WSState.Loading());

    count += 1;
    var actions = {};
    messages[count] = actions;
    var sendprocess = yield fork(
      processWsSend,
      commandch,
      sendch,
      actions,
      defaultonerror
    );
    var receiveprocess = yield fork(processWsReceive, receivech, actions);
    yield call(startWS, url, count, sendch, receivech, actions);
    yield cancel(sendprocess);
    yield cancel(receiveprocess);

    var ids = Object.keys(actions);
    for (var i = 0; i < ids.length; i++) {
      var action = actions[ids[i]];
      if (action.timeouter) {
        yield cancel(action.timeouter);
      }

      var response = action.onerror({
        error: "Lost connection to the server",
        error_code: "LostConnection"
      });
      if (response) {
        yield put(response);
      }
    }

    delete messages[count];
    yield delay(delayMS || 5000);
  }
}
