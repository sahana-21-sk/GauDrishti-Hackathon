# results.json: the ONE contract between Person A and Person B (frozen in hour 0)
Paths (clip, processed_video) are relative to the folder holding results.json.
```
meta:   schema_version, video_name, fps, duration_s, width, height, baseline_until_s, video_start_clock "HH:MM", processed_video
cows:   [ {id, stats:{baseline:{speed,lying_pct,feeding_pct}, recent:{...}, isolation_score, mount_events, heat_score, health_score},
           timeline:[{t, state(walking|feeding|lying|standing), speed, x, y}]} ]      x,y are 0-1 fractions of the frame
events: [ {t_start, t_end, type:"mounting", upper_id, lower_id} ]
watchlist: [ {id:"W1", cow_id, score 0-1, t, reasons:[text], clip:"clips/x.mp4", clip_start, clip_dur} ]
alerts: [ {id:"A1", cow_id, type:"heat"|"health", score 0-1, t, reasons:[text], clip:"clips/x.mp4", clip_start, clip_dur} ]
```
Reference example: data/demo/results.json. If you must change the format, tell your teammate FIRST and update this file.
