var register = require("@babel/register");

register({
  presets: ["@babel/preset-env", "@babel/preset-typescript"],
  extensions: [".js", ".jsx", ".ts", ".tsx"],
});

var config = require("./webpack.config.ts");
module.exports = config;
