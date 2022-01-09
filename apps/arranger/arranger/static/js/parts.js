import { useState } from "react";
import { Group, Layer, Line, Rect } from "react-konva";
import { useDispatch, useSelector } from "react-redux";
import { PartState } from "./state.js";

var PartPixels = ({ part, pixelWidth, lineWidth }) => {
  let x = (col) => col * pixelWidth;
  let y = (row) => row * pixelWidth;

  return (
    <Group>
      {part.pixels.map((pixel) => {
        return (
          <Rect
            key={pixel.key}
            width={pixelWidth}
            height={pixelWidth}
            x={x(pixel.col)}
            y={y(pixel.row)}
            fill={pixel.color}
          />
        );
      })}
      <Line
        stroke="white"
        strokeWidth={lineWidth}
        points={[
          x(0),
          y(0),
          x(part.width),
          y(0),
          x(part.width),
          y(part.height),
          x(0),
          y(part.height),
          x(0),
          y(0),
        ]}
      />
    </Group>
  );
};

var Part = ({ part, zero_x, zero_y, pixelWidth, partWidth }) => {
  var dispatch = useDispatch();

  var [position, setPosition] = useState({ x: 0, y: 0 });

  var start_x = zero_x + part.user_x * pixelWidth;
  var start_y = zero_y - part.user_y * pixelWidth;
  var lineWidth = Math.max(Math.floor(pixelWidth / 2), 1);

  var onDragEnd = () => {
    var user_x = (position.x - zero_x) / pixelWidth;
    var user_y = (zero_y - position.y) / pixelWidth;
    dispatch(
      PartState.ChangePosition({
        serial: part.serial,
        part_number: part.part_number,
        user_x,
        user_y,
      })
    );
  };

  var dragBound = (pos) => {
    var newpos = {
      x: pos.x - ((pos.x - zero_x) % pixelWidth),
      y: pos.y - ((pos.y - zero_y) % pixelWidth),
    };
    setPosition(newpos);
    return newpos;
  };

  return (
    <Group
      x={start_x}
      y={start_y}
      draggable={true}
      onDragEnd={onDragEnd}
      dragBoundFunc={dragBound}
      onClick={() =>
        dispatch(PartState.Highlight(part.serial, part.part_number))
      }
      onTap={() => dispatch(PartState.Highlight(part.serial, part.part_number))}
    >
      <PartPixels
        serial={part.serial}
        part={part}
        pixelWidth={pixelWidth}
        lineWidth={lineWidth}
        partWidth={partWidth}
      />
    </Group>
  );
};

export default (props) => {
  var parts = useSelector((state) => state.parts.parts);

  return (
    <Layer>
      {parts.map((part) => (
        <Part key={part.key} part={part} {...props} />
      ))}
    </Layer>
  );
};
