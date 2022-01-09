import { applyMiddleware, combineReducers, createStore } from "redux";
import { devToolsEnhancer } from "redux-devtools-extension";
import createSagaMiddleware from "redux-saga";
import { partsSaga, PartState } from "./state.js";
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
