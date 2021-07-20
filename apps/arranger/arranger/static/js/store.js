import { devToolsEnhancer } from "redux-devtools-extension";
import { applyMiddleware, createStore } from "redux";
import createSagaMiddleware from "redux-saga";
import { combineReducers } from "redux";

import { PartState, partsSaga } from "./state.js";
import { WSState } from "./wsclient.js";

export const makeReducer = (extra) => {
  return combineReducers({
    ...extra,
    wsclient: WSState.reducer(),
    parts: PartState.reducer(),
  });
};

export const makeSagaMiddleware = () => {
  return createSagaMiddleware();
};

export const makeStore = (reducer, sagaMiddleware) => {
  const creator = applyMiddleware(sagaMiddleware)(createStore);
  return creator(reducer, devToolsEnhancer());
};

export const runSagaMiddleware = (sagaMiddleware) => {
  sagaMiddleware.run(partsSaga);
};
