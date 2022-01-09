import "core-js";
import { render } from "react-dom";
import { Provider } from "react-redux";
import { fork } from "redux-saga/effects";
import Page from "./page.js";
import {
  makeReducer,
  makeSagaMiddleware,
  makeStore,
  runSagaMiddleware,
} from "./store.js";
import { listen } from "./wsclient.js";

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

render(
  <Provider store={store}>
    <Page />
  </Provider>,
  document.getElementById("page")
);
