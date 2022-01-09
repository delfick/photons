import ESLintPlugin from "eslint-webpack-plugin";
import HtmlWebpackPlugin from "html-webpack-plugin";
import path from "path";
import RemovePlugin from "remove-files-webpack-plugin";
import webpack, { Configuration } from "webpack";

const environment =
  process.env.NODE_ENV == "production" || process.env.NODE_ENV == "staging"
    ? "production"
    : "development";

var prefix = environment == "development" ? "dev" : "prod";

var publicPath = (p: string) => (url: string) => {
  return `/static/${p}/${url}`;
};

var outputPath = (p: string) => (url: string) => {
  return `${p}/${url}`;
};

var name = () => {
  if (environment === "development") {
    return "[path][name].[ext]";
  }

  return "[contenthash].[ext]";
};

const config: Configuration = {
  mode: environment,

  entry: ["./js/index.js"],

  output: {
    filename: `app.${
      environment == "development" ? "[name]" : "[contenthash]"
    }.js`,
    path: path.resolve(__dirname, "dist", prefix, "static"),
    publicPath: "/static",
  },

  devtool:
    environment == "development" ? "eval-source-map" : "eval-cheap-source-map",

  optimization: {
    splitChunks: {
      chunks: "all",
    },
  },

  performance: {
    hints: false,
  },

  plugins: [
    new ESLintPlugin(),
    new RemovePlugin({
      before: {
        include: environment == "development" ? [] : ["./dist/prod"],
      },
    }),
    new webpack.DefinePlugin({
      "process.env.NODE_ENV": JSON.stringify(environment),
    }),
    new webpack.ProvidePlugin({ React: "react" }),
    new HtmlWebpackPlugin({
      template: "index.ejs",
      filename: "../index.html",
    }),
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
            publicPath: publicPath("manifest"),
          },
        },
      },
      {
        test: /\.ico$/,
        use: {
          loader: "file-loader",
          options: {
            name,
            outputPath: outputPath("icons"),
            publicPath: publicPath("icons"),
          },
        },
      },
      {
        test: /\.(png|jpg|svg)$/,
        use: {
          loader: "file-loader",
          options: {
            name,
            outputPath: outputPath("images"),
            publicPath: publicPath("images"),
          },
        },
      },
      {
        test: /\.css$/,
        use: {
          loader: "file-loader",
          options: {
            name,
            outputPath: outputPath("css"),
            publicPath: publicPath("css"),
          },
        },
      },
      {
        test: /\.jsx?$/,
        exclude: /node_modules/,
        loader: "babel-loader",
      },
    ],
  },
};

export default config;
