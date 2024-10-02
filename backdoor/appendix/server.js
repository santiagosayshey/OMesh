const express = require("express");
const bodyParser = require("body-parser");
const cors = require("cors");
const app = express();
const port = 3000;

app.use(cors());
app.use(bodyParser.json());

app.post("/return", (req, res) => {
  console.log("Received POST request at /return");
  console.log("Request body:", req.body);
  res.status(200).send("Request received and logged");
});

app.listen(port, () => {
  console.log(`Server listening at http://localhost:${port}`);
});
