import { createAction, createReducer } from "redux-act";
import { put, select, takeEvery, takeLatest } from "redux-saga/effects";
import { WSCommand, WSState } from "./wsclient.js";

var combine_parts = (parts, existing) => {
  var by_key = {};
  existing.map((part) => {
    by_key[part.key] = part;
  });

  var result = [];
  var anyDifferent = false;

  parts.map((part) => {
    if (!by_key[part.key]) {
      by_key[part.key] = {};
    }

    var nxt = { ...by_key[part.key], ...part };

    var different = false;
    Object.keys(nxt).map((attr) => {
      if (by_key[part.key][attr] != nxt[attr]) {
        different = true;
      }
    });

    if (different) {
      result.push(nxt);
      anyDifferent = true;
    } else {
      result.push(by_key[part.key]);
    }
  });

  if (anyDifferent) {
    return result;
  } else {
    return existing;
  }
};

class PartsStateKls {
  Error = createAction(
    "Failed to interact with the server",
    ({ namespace, error, error_code, reason, original }) => {
      if (!reason) {
        reason = original.type.substr(original.type.indexOf("] ") + 2);
        if (original.reason) {
          reason = original.reason;
        }
      }

      reason = `${error_code}: Failure while ${reason}`;

      if (typeof error !== "string" && !(error instanceof String)) {
        error = JSON.stringify(error);
      }

      return { namespace, reason, error, original };
    }
  );

  ClearError = createAction("Clear error");

  MakeStream = createAction("Make a stream");
  StartedStream = createAction("Started a stream", (messageId) => ({
    messageId,
  }));
  LoadingStream = createAction("Loading a stream");
  StreamProgress = createAction("Progress from a stream");

  Highlight = createAction("highlight a part", (serial, part_number) => ({
    serial,
    part_number,
  }));

  GotParts = createAction("Got parts");
  ChangePosition = createAction("Change Position");

  reducer() {
    return createReducer(
      {
        [this.Error]: (state, error) => {
          return { ...state, error };
        },
        [this.ClearError]: (state) => {
          return { ...state, error: undefined };
        },
        [this.StartedStream]: (state, { messageId }) => {
          return { ...state, loading: false, messageId };
        },
        [WSState.Error]: (state) => {
          return { ...state, loading: false, parts: [] };
        },
        [this.LoadingStream]: (state) => {
          return {
            ...state,
            loading: true,
            error: undefined,
            parts: [],
            messageId: undefined,
          };
        },
        [this.GotParts]: (state, parts) => {
          return {
            ...state,
            parts: combine_parts(parts, state.parts),
            waiting: false,
          };
        },
      },
      {
        parts: [],
        error: undefined,
        waiting: true,
        loading: false,
        messageId: undefined,
      }
    );
  }
}

export const PartState = new PartsStateKls();

function* wsConnectedSaga() {
  yield put(PartState.MakeStream());
}

function* changePositionSaga(original) {
  let messageId = yield select((state) => state.parts.messageId);
  if (!messageId) {
    return;
  }

  yield put(
    WSCommand(
      "/v1/lifx/command",
      {
        command: "change_position",
        args: original.payload,
      },
      { onerror: PartState.Error, original, parentMessageIds: [messageId] }
    )
  );
}

function* highlightSaga(original) {
  let messageId = yield select((state) => state.parts.messageId);
  if (!messageId) {
    return;
  }

  yield put(
    WSCommand(
      "/v1/lifx/command",
      {
        command: "highlight",
        args: original.payload,
      },
      { onerror: PartState.Error, original, parentMessageIds: [messageId] }
    )
  );
}

function* makePartStreamSaga(original) {
  let loading = yield select((state) => state.parts.loading);
  if (loading) {
    return;
  }

  let onsuccess = PartState.LoadingStream;
  let onerror = PartState.Error;
  let onprogress = PartState.StreamProgress;

  yield put(PartState.LoadingStream());

  yield put(
    WSCommand(
      "/v1/lifx/command",
      {
        command: "parts/store",
      },
      { onsuccess, onprogress, onerror, original }
    )
  );
}

function* streamProgressSaga(command) {
  let { payload } = command;

  if (payload.progress.error) {
    yield put(
      PartState.Error({
        ...payload.progress,
        original: { type: "[] processing device discovery" },
      })
    );
    return;
  }

  let instruction = payload.progress.instruction;

  if (instruction == "started") {
    yield put(PartState.StartedStream(payload.messageId));
  } else if (instruction == "parts") {
    yield put(PartState.GotParts(payload.progress.parts));
  }
}

export function* partsSaga() {
  yield takeEvery(PartState.StreamProgress, streamProgressSaga);
  yield takeEvery(PartState.Highlight, highlightSaga);
  yield takeEvery(PartState.ChangePosition, changePositionSaga);

  yield takeLatest(PartState.MakeStream, makePartStreamSaga);
  yield takeLatest(WSState.Connected, wsConnectedSaga);
}
