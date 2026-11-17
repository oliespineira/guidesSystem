// Where the two services live. This file is for local use with compose;
// on deploy, the pipeline writes its own config.js with the Azure URLs.
window.CONFIG = {
  KRAAL_URL: "http://localhost:8001",
  ACTAS_URL: "http://localhost:8002",
};