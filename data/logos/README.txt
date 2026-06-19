Default team logos (built-in league)

Place one image per school here, OR run:

  python scripts/import_default_logos.py "PATH\TO\YOUR\LOGO\FOLDER"

Master folder path (optional): data/game_logos_source.txt
To refresh WV-named schools from that folder:

  python scripts/sync_wv_team_logos.py

Naming (any of these work):
  - Full school name: Huntington.png
  - Abbreviation from teams.json: HNT.png
  - With suffix: Huntington_logo.webp

Supported formats: .png, .jpg, .jpeg, .webp

The API serves these when a user has not uploaded their own logo for that school.
User-uploaded logos in saves/{user_id}/_logos/ take priority.
