const RemovePlugin = require("remove-files-webpack-plugin");
var HtmlWebpackPlugin = require("html-webpack-plugin");
var webpack = require("webpack");
var path = require("path");

var mode = process.env.NODE_ENV || "development";

var prefix = mode == "development" ? "dev" : "prod";

var publicPath = p => (url, resourcePath, resourceQuery) => {
  return `/static/${p}/${url}`;
};

var outputPath = p => (url, resourcePath, resourceQuery) => {
  return `${p}/${url}`;
};

var name = (resourcePath, resourceQuery) => {
  if (mode === "development") {
    return "[path][name].[ext]";
  }

  return "[contenthash].[ext]";
};

module.exports = {
  mode: mode,
  entry: ["./js/index.js"],
  output: {
    filename: `app.${mode == "development" ? "" : "[contenthash]"}.js`,
    path: path.resolve(__dirname, "dist", prefix, "static"),
    publicPath: "/static"
  },
  devtool: mode == "development" ? "eval-source-map" : "eval-cheap-source-map",
  optimization: {
    splitChunks: {
      chunks: "all"
    }
  },
  performance: {
    hints: false
  },
  plugins: [
    new RemovePlugin({
      before: {
        include: mode == "development" ? [] : ["./dist/prod"]
      }
    }),
    new webpack.DefinePlugin({
      "process.env.NODE_ENV": JSON.stringify(mode)
    }),
    new webpack.ProvidePlugin({ React: "react" }),
    new HtmlWebpackPlugin({
      template: "index.ejs",
      filename: "../index.html"
    })
  ],
  module: {
    rules: [
      {
        test: /\.webmanifest$/,
        use: {
          loader: "file-loader",
          options: {
            name,
            outputPath: outputPath("manifest"),
            publicPath: publicPath("manifest")
          }
        }
      },
      {
        test: /\.ico$/,
        use: {
          loader: "file-loader",
          options: {
            name,
            outputPath: outputPath("icons"),
            publicPath: publicPath("icons")
          }
        }
      },
      {
        test: /\.(png|jpg|svg)$/,
        use: {
          loader: "file-loader",
          options: {
            name,
            outputPath: outputPath("images"),
            publicPath: publicPath("images")
          }
        }
      },
      {
        test: /\.css$/,
        use: {
          loader: "file-loader",
          options: {
            name,
            outputPath: outputPath("css"),
            publicPath: publicPath("css")
          }
        }
      },
      {
        test: /\.jsx?$/,
        exclude: /node_modules/,
        use: [
          {
            loader: "babel-loader",
            options: {
              plugins: ["transform-class-properties"],
              presets: ["@babel/preset-env", "@babel/preset-react"]
            }
          }
        ]
      }
    ]
  }
};
