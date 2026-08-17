# Custom feeds

A small collection of custom feeds for public sources that do not provide a convenient native feed.

## Available feeds

### SlovLit

Full-text JSON Feed generated from the public SlovLit mailing-list archive. Digest messages are formatted into readable blocks with separate sender, recipient, date and subject fields.

**Feeder / JSON Feed:**

`https://raw.githubusercontent.com/hulln/custom-feeds/main/slovlit/feed.json`

Source: https://mailman.ijs.si/pipermail/slovlit/

### Center Digitalna UL

JSON Feed for the AI-in-education updates published by Center Digitalna UL.

**Feeder / JSON Feed:**

`https://raw.githubusercontent.com/hulln/custom-feeds/main/digitalna-ul/feed.json`

Source: https://www.uni-lj.si/studij/center-digitalna-ul/gradiva/namigi-in-triki/aktualno-dogajanje-na-podrocju-ui-v-izobrazevanju

## Structure

```text
custom-feeds/
├── slovlit/
│   ├── update_feed.py
│   ├── update_json.py
│   ├── feed.xml
│   └── feed.json
├── digitalna-ul/
│   ├── update_feed.py
│   └── feed.json
└── .github/workflows/update-feed.yml
```

Feeds are regenerated automatically with GitHub Actions every four hours.
