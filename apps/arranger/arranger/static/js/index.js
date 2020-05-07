import "regenerator-runtime/runtime";
import "core-js/stable";

import { fork } from "redux-saga/effects";
import { Provider } from "react-redux";
import ReactDOM from "react-dom";
import React from "react";

import { listen } from "./wsclient.js";
import Page from "./page.js";
import {
  makeReducer,
  makeSagaMiddleware,
  makeStore,
  runSagaMiddleware
} from "./store.js";

const reducer = makeReducer();
const sagaMiddleware = makeSagaMiddleware();
const store = makeStore(reducer, sagaMiddleware);
runSagaMiddleware(sagaMiddleware);

var scheme = "ws";
if (window.location.protocol.startsWith("https")) {
  scheme = "wss";
}
var url =
  scheme +
  "://" +
  window.location.hostname +
  ":" +
  String(window.location.port) +
  "/v1/ws";

function* mainSaga() {
  yield fork(listen, url);
}

sagaMiddleware.run(mainSaga);

ReactDOM.render(
  <Provider store={store}>
    <Page />
  </Provider>,
  document.getElementById("page")
);
