<div align="center">

# Re:log

Research logbook for collaborative daily lab notes.

</div>

A simple web interface to an append-only logbook database.
You cannot delete or modify log posts once submitted,
only cross them out.

# Features

- **Record log entry**:
  - Note,
  - Authors,
  - Upload file attachments, pictures rendered automatically.
  - Date and time, defaults to current.
    - Real time of submission is also saved.
- **View logs** and **search** them by:
  - Log number,
  - Author,
  - Date range,
  - Containing text in note.
- View image attachments in gallery.
- Jump to next day, previous day, or today.
- Cross out log post.

# Install

Run locally in development mode with the following commands:

``` sh
git clone https://github.com/Pocar-lab/relog
cd relog
pip install -r requirements.txt
python logbook.py
```

Then navigate to given URL in your web browser.

# References

1. C. Gross, A. Stepinski, and D. Akşimşek, *Hypermedia systems*, 2023, https://hypermedia.systems/
2. Python Software Foundation, *Python*, version 3.14.3, 2026, https://www.python.org
3. Pallets, *Flask*, version 3.1.3, 2026, https://flask.palletsprojects.com/
4. SQLite Consortium, *SQLite*, version 3.50.2, 2026, https://www.sqlite.org/

## AI Use

Claude Sonnet 5.5 was used in initial research stage, for debugging, and as a search engine.
No generative AI was used to write significant code or prose.
