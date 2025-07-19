from flask import Flask, request, redirect, url_for, session, send_from_directory, render_template_string, jsonify
from datetime import datetime, timedelta
import hashlib
import os
import time
import glob
import json

from db_utils import initialize_database
initialize_database()


import os

# Ensure uploads folder exists
os.makedirs('backend/uploads', exist_ok=True)


app = Flask(__name__, static_folder='static', static_url_path='/static')
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


app.secret_key = 'very_secret_key'  # Required for sessions
# Hardcoded admin credentials
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'restroomads123'


def calculate_uptime_percent(screen_id):
    conn = sqlite3.connect('db.sqlite')
    c = conn.cursor()

    now = datetime.now()
    start_time = now - timedelta(hours=24)
    start_time_str = start_time.strftime("%Y-%m-%d %H:%M:%S")

    c.execute("SELECT COUNT(*) FROM pings WHERE screen_id = ? AND timestamp >= ?", (screen_id, start_time_str))
    ping_count = c.fetchone()[0]
    conn.close()

    duration_seconds = (datetime.now() - start_time).total_seconds()
    expected_pings = max(1, duration_seconds // 30)

    uptime_percent = (ping_count / expected_pings) * 100
    return round(uptime_percent, 1)



@app.route('/')
def index():
    if session.get('logged_in'):
        return send_from_directory('static', 'dashboard.html')
    return send_from_directory('static', 'index.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        session['logged_in'] = True
        return redirect(url_for('index'))
    return "Invalid credentials", 401

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

import sqlite3

@app.route('/screens')
def screens():
    if not session.get('logged_in'):
        return redirect(url_for('index'))

    conn = sqlite3.connect('db.sqlite')
    c = conn.cursor()
    c.execute('SELECT id, name, area, building, floor, restroom, status FROM screens')
    screens = c.fetchall()
    conn.close()

    html = '''
    <!DOCTYPE html>
    <html><head><title>Screens</title>
    <script src="https://cdn.tailwindcss.com"></script></head>
    <body class="p-8 bg-gray-100 text-gray-800">
      <h1 class="text-3xl font-bold mb-6">📺 Registered Screens</h1>
      <table class="w-full bg-white shadow rounded-xl">
        <thead class="bg-gray-200 text-left text-sm font-semibold">
          <tr><th class="p-3">Name</th><th class="p-3">Location</th><th class="p-3">Status</th><th class="p-3">Actions</th></tr>
        </thead><tbody>
    '''

    for s in screens:
        html += f'''
        <tr class="border-t">
        <td class="p-3">{s[1]}</td>
        <td class="p-3">{s[2]} / {s[3]} / {s[4]} / {s[5]}</td>
        <td class="p-3">{s[6]}</td>
        <td class="p-3">
            <form action="/delete-screen/{s[0]}" method="POST" onsubmit="return confirm('Delete this screen?');">
            <button class="text-red-600 hover:underline" type="submit">Delete</button>
            </form>
        </td>
        </tr>
        '''


    html += '''
        </tbody></table>
      <a href="/add-screen" class="mt-6 inline-block bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">+ Add Screen</a>
      <a href="/" class="ml-4 inline-block text-blue-500">⬅ Back to Dashboard</a>
    </body></html>
    '''

    return html


@app.route('/add-screen', methods=['GET', 'POST'])
def add_screen():
    if not session.get('logged_in'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form.get('name')
        area = request.form.get('area')
        building = request.form.get('building')
        floor = request.form.get('floor')
        restroom = request.form.get('restroom')
        group_id = request.form.get('restroom')  # simple grouping by restroom

        conn = sqlite3.connect('db.sqlite')
        c = conn.cursor()
        c.execute('''
            INSERT INTO screens (name, area, building, floor, restroom, group_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, area, building, floor, restroom, group_id))
        conn.commit()
        conn.close()
        return redirect(url_for('screens'))

    # Render form
    form = '''
    <!DOCTYPE html><html><head><title>Add Screen</title>
    <script src="https://cdn.tailwindcss.com"></script></head>
    <body class="p-8 bg-gray-100 text-gray-800">
      <h1 class="text-2xl font-bold mb-6">➕ Add New Screen</h1>
      <form method="POST" class="space-y-4 bg-white p-6 rounded shadow max-w-md">
        <input name="name" placeholder="Screen Name" required class="w-full px-4 py-2 border rounded" />
        <input name="area" placeholder="Area" class="w-full px-4 py-2 border rounded" />
        <input name="building" placeholder="Building" class="w-full px-4 py-2 border rounded" />
        <input name="floor" placeholder="Floor" class="w-full px-4 py-2 border rounded" />
        <input name="restroom" placeholder="Restroom" class="w-full px-4 py-2 border rounded" />
        <button type="submit" class="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700">Add Screen</button>
      </form>
      <a href="/screens" class="inline-block mt-4 text-blue-500">⬅ Back to Screens</a>
    </body></html>
    '''
    return form

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'mp4'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/content', methods=['GET', 'POST'])
def content():
    if not session.get('logged_in'):
        return redirect(url_for('index'))

    message = ""

    if request.method == 'POST':
        file = request.files.get('file')
        tags = request.form.get('tags', '')
        category = request.form.get('category', '')
        expires_on = request.form.get('expires_on', '')

        if file and allowed_file(file.filename):
            filename = file.filename
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            content_type = 'video' if filename.lower().endswith('mp4') else 'image'

            conn = sqlite3.connect('db.sqlite')
            c = conn.cursor()
            c.execute('''
                INSERT INTO content (filename, content_type, tags, category, expires_on)
                VALUES (?, ?, ?, ?, ?)
            ''', (filename, content_type, tags, category, expires_on))
            conn.commit()
            conn.close()

            message = "✅ File uploaded successfully."
        else:
            message = "❌ Invalid file type."

    # Show content list
    conn = sqlite3.connect('db.sqlite')
    c = conn.cursor()
    c.execute('SELECT id, filename, content_type, tags, category, expires_on FROM content ORDER BY id DESC')
    content_items = c.fetchall()
    conn.close()

    html = f'''
    <!DOCTYPE html>
    <html><head><title>Content</title>
    <script src="https://cdn.tailwindcss.com"></script></head>
    <body class="p-8 bg-gray-100 text-gray-800">
      <h1 class="text-3xl font-bold mb-6">🗂️ Content Library</h1>
      <form method="POST" enctype="multipart/form-data" class="space-y-4 bg-white p-6 rounded shadow max-w-xl">
        <p class="text-green-600">{message}</p>
        <input type="file" name="file" required class="block w-full border rounded px-4 py-2" />
        <input type="text" name="tags" placeholder="Tags (comma-separated)" class="block w-full border rounded px-4 py-2" />
        <input type="text" name="category" placeholder="Category" class="block w-full border rounded px-4 py-2" />
        <input type="date" name="expires_on" class="block w-full border rounded px-4 py-2" />
        <button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">Upload</button>
      </form>

      <h2 class="text-2xl font-semibold mt-10 mb-4">📋 Uploaded Content</h2>
      <table class="w-full bg-white shadow rounded-xl text-sm">
        <thead class="bg-gray-200"><tr>
          <th class="p-3 text-left">File</th>
          <th class="p-3 text-left">Type</th>
          <th class="p-3 text-left">Tags</th>
          <th class="p-3 text-left">Category</th>
          <th class="p-3 text-left">Expires</th>
          <th class="p-3">Actions</th>

        </tr></thead><tbody>
    '''

    for item in content_items:
        html += f'''
        <tr class="border-t">
        <td class="p-3">{item[1]}</td>
        <td class="p-3">{item[2]}</td>
        <td class="p-3">{item[3]}</td>
        <td class="p-3">{item[4]}</td>
        <td class="p-3">{item[5]}</td>
        <td class="p-3">
            <form action="/delete-content/{item[0]}" method="POST" onsubmit="return confirm('Delete this content?');">
            <button class="text-red-600 hover:underline" type="submit">Delete</button>
            </form>
        </td>
        </tr>
        '''


    html += '''
        </tbody></table>
      <a href="/" class="mt-6 inline-block text-blue-500">⬅ Back to Dashboard</a>
    </body></html>
    '''

    return html


@app.route('/assign', methods=['GET', 'POST'])
def assign():
    if not session.get('logged_in'):
        return redirect(url_for('index'))

    conn = sqlite3.connect('db.sqlite')
    c = conn.cursor()

    # Fetch all screens and content
    c.execute('SELECT id, name FROM screens')
    screens = c.fetchall()

    c.execute('SELECT id, filename FROM content')
    content = c.fetchall()

    message = ""

    if request.method == 'POST':
        screen_id = request.form.get('screen_id')
        content_id = request.form.get('content_id')
        play_order = request.form.get('play_order', 1)
        start_time = request.form.get('start_time', '')
        end_time = request.form.get('end_time', '')

        c.execute('''
            INSERT INTO screen_content (screen_id, content_id, play_order, start_time, end_time)
            VALUES (?, ?, ?, ?, ?)
        ''', (screen_id, content_id, play_order, start_time, end_time))
        conn.commit()
        message = "✅ Assigned successfully."

    # Show existing assignments
    c.execute('''
        SELECT s.name, c.filename, sc.play_order, sc.start_time, sc.end_time, sc.screen_id, sc.content_id
        FROM screen_content sc
        JOIN screens s ON s.id = sc.screen_id
        JOIN content c ON c.id = sc.content_id
        ORDER BY s.name, sc.play_order
    ''')

    assignments = c.fetchall()

    conn.close()

    html = f'''
    <!DOCTYPE html>
    <html><head><title>Assign Content</title>
    <script src="https://cdn.tailwindcss.com"></script></head>
    <body class="p-8 bg-gray-100 text-gray-800">
      <h1 class="text-3xl font-bold mb-6">📌 Assign Content to Screens</h1>
      <form method="POST" class="bg-white p-6 rounded shadow space-y-4 max-w-xl">
        <p class="text-green-600">{message}</p>
        <select name="screen_id" class="w-full px-4 py-2 border rounded">
            <option disabled selected>-- Select Screen --</option>
            {''.join([f'<option value="{s[0]}">{s[1]}</option>' for s in screens])}
        </select>
        <select name="content_id" class="w-full px-4 py-2 border rounded">
            <option disabled selected>-- Select Content --</option>
            {''.join([f'<option value="{c[0]}">{c[1]}</option>' for c in content])}
        </select>
        <input type="number" name="play_order" placeholder="Play Order" class="w-full px-4 py-2 border rounded" />
        <input type="time" name="start_time" class="w-full px-4 py-2 border rounded" />
        <input type="time" name="end_time" class="w-full px-4 py-2 border rounded" />
        <button type="submit" class="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">Assign</button>
      </form>

      <h2 class="text-2xl font-semibold mt-10 mb-4">📋 Assignments</h2>
      <table class="w-full bg-white shadow rounded-xl text-sm">
        <thead class="bg-gray-200"><tr>
          <th class="p-3 text-left">Screen</th>
          <th class="p-3 text-left">Content</th>
          <th class="p-3 text-left">Order</th>
          <th class="p-3 text-left">Start</th>
          <th class="p-3 text-left">End</th>
          <th class="p-3 text-left">Actions</th>
        </tr></thead><tbody>
    '''

    for a in assignments:
        html += f'''
        <tr class="border-t">
        <td class="p-3">{a[0]}</td>
        <td class="p-3">{a[1]}</td>
        <td class="p-3">{a[2]}</td>
        <td class="p-3">{a[3]}</td>
        <td class="p-3">{a[4]}</td>
        <td class="p-3">
            <form action="/remove-assignment/{a[5]}/{a[6]}" method="POST" onsubmit="return confirm('Remove this assignment?');">
            <button class="text-red-600 hover:underline" type="submit">Remove</button>
            </form>
        </td>
        </tr>
        '''

    html += '''
        </tbody></table>
      <a href="/" class="mt-6 inline-block text-blue-500">⬅ Back to Dashboard</a>
    </body></html>
    '''

    return html

@app.route('/delete-screen/<int:id>', methods=['POST'])
def delete_screen(id):
    if not session.get('logged_in'):
        return redirect(url_for('index'))

    conn = sqlite3.connect('db.sqlite')
    c = conn.cursor()
    c.execute('DELETE FROM screens WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('screens'))


@app.route('/delete-content/<int:id>', methods=['POST'])
def delete_content(id):
    if not session.get('logged_in'):
        return redirect(url_for('index'))

    # Delete file from uploads
    conn = sqlite3.connect('db.sqlite')
    c = conn.cursor()
    c.execute('SELECT filename FROM content WHERE id = ?', (id,))
    row = c.fetchone()
    if row:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], row[0])
        if os.path.exists(filepath):
            os.remove(filepath)

    c.execute('DELETE FROM content WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('content'))

@app.route('/remove-assignment/<int:screen_id>/<int:content_id>', methods=['POST'])
def remove_assignment(screen_id, content_id):
    if not session.get('logged_in'):
        return redirect(url_for('index'))

    conn = sqlite3.connect('db.sqlite')
    c = conn.cursor()
    c.execute('DELETE FROM screen_content WHERE screen_id = ? AND content_id = ?', (screen_id, content_id))
    conn.commit()
    conn.close()
    return redirect(url_for('assign'))




@app.route('/api/playlist/<int:screen_id>', methods=['GET'])
def get_playlist(screen_id):
    conn = sqlite3.connect('db.sqlite')
    c = conn.cursor()

    # Remove expired content assignments
    c.execute('''
        DELETE FROM screen_content
        WHERE content_id IN (
            SELECT id FROM content
            WHERE expires_on IS NOT NULL AND date(expires_on) <= date('now')
        )
    ''')
    conn.commit()


    # Get screen's group_id
    c.execute('SELECT group_id FROM screens WHERE id = ?', (screen_id,))
    group_row = c.fetchone()
    group_id = group_row[0] if group_row else None

    # Filter out expired content
    c.execute('''
        SELECT c.filename
        FROM screen_content sc
        JOIN content c ON sc.content_id = c.id
        WHERE sc.screen_id = ?
        AND (c.expires_on IS NULL OR date(c.expires_on) > date('now'))
        ORDER BY sc.play_order ASC
    ''', (screen_id,))

    items = c.fetchall()
    conn.close()

    playlist = [{"filename": row[0]} for row in items]
      # Calculate hash
    hash_input = ''.join(item['filename'] for item in playlist)
    playlist_hash = hashlib.md5(hash_input.encode()).hexdigest()

    return jsonify({
        "playlist": playlist,
        "group_id": group_id,
        "hash": playlist_hash
    })



@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('index'))
    
    mark_offline_screens()  # ✅ Call this before fetching

    conn = sqlite3.connect('db.sqlite')
    c = conn.cursor()
    c.execute("SELECT id, name, area, building, floor, restroom, status, last_seen FROM screens")
    screens = c.fetchall()
    snapshots = {}
    for s in screens:
        sid = s[0]
        pattern = os.path.join(app.root_path, 'snapshots', f'screen_{sid}_*.png')
        files = glob.glob(pattern)
        if files:
            latest = max(files, key=os.path.getctime)
            snapshots[sid] = os.path.basename(latest)

    conn.close()

    html = '''
    <!DOCTYPE html>
    <html><head><title>Screen Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="p-8 bg-gray-100 text-gray-800">
      <h1 class="text-3xl font-bold mb-6">📺 Screen Status Dashboard</h1>
      <table class="w-full bg-white shadow rounded-xl text-sm">
        <thead class="bg-gray-200">
          <tr>
            <th class="p-3 text-left">ID</th>
            <th class="p-3 text-left">Name</th>
            <th class="p-3 text-left">Location</th>
            <th class="p-3 text-left">Status</th>
            <th class="p-3 text-left">Last Seen</th>
            <th class="p-3 text-left">Actions</th>
            <th class="p-3 text-left">Snapshot</th>
            <th class="p-3 text-left">Uptime (24h)</th>
          </tr>
        </thead>
        <tbody>
    '''

    for s in screens:
        location = f"{s[2]} / {s[3]} / {s[4]} / {s[5]}"
        status_color = "text-green-600" if s[6] == 'online' else "text-red-600"
        uptime = calculate_uptime_percent(s[0])
        html += f'''
        <tr class="border-t">
          <td class="p-3">{s[0]}</td>
          <td class="p-3 font-semibold">{s[1]}</td>
          <td class="p-3">{location}</td>
          <td class="p-3 font-bold {status_color}">{s[6].capitalize()}</td>
          <td class="p-3">{s[7]}</td>
          <td class="p-3">
            <form action="/manual-snapshot" method="POST" style="display:inline;">
              <input type="hidden" name="screen_id" value="{s[0]}" />
              <button class="text-blue-600 hover:underline" type="submit">📸 Snapshot</button>
            </form>
            <form action="/manual-sync" method="POST" style="display:inline; margin-left: 10px;">
              <input type="hidden" name="screen_id" value="{s[0]}" />
              <button class="text-purple-600 hover:underline" type="submit">🔁 Restart Sync</button>
            </form>
          </td>
                <td class="p-3">
        {f'<img src="/snapshots/{snapshots[s[0]]}" width="100">' if s[0] in snapshots else 'N/A'}
          </td>
          <td class="p-3">{uptime}%</td>

        </tr>
        '''

    html += '''
        </tbody></table>
        <a href="/" class="mt-6 inline-block text-blue-500">⬅ Back to Home</a>
    </body></html>
    '''

    return html


@app.route('/manual-snapshot', methods=['POST'])
def manual_snapshot():
    screen_id = request.form.get('screen_id')
    if not screen_id:
        return "Missing screen_id", 400

    conn = sqlite3.connect('db.sqlite')
    c = conn.cursor()

    # Insert or update the screen_flags row for this screen_id
    c.execute('''
        INSERT INTO screen_flags (screen_id, force_snapshot)
        VALUES (?, 1)
        ON CONFLICT(screen_id) DO UPDATE SET force_snapshot=1
    ''', (screen_id,))
    conn.commit()
    conn.close()

    print(f"📸 Manual snapshot flag set for screen {screen_id}")
    return redirect(url_for('dashboard'))


@app.route('/manual-sync', methods=['POST'])
def manual_sync():
    screen_id = request.form.get('screen_id')
    if not screen_id:
        return "Missing screen_id", 400

    conn = sqlite3.connect('db.sqlite')
    c = conn.cursor()

    # Insert or update the screen_flags row for this screen_id
    c.execute('''
        INSERT INTO screen_flags (screen_id, force_resync)
        VALUES (?, 1)
        ON CONFLICT(screen_id) DO UPDATE SET force_resync=1
    ''', (screen_id,))
    conn.commit()
    conn.close()

    print(f"🔁 Manual sync flag set for screen {screen_id}")
    return redirect(url_for('dashboard'))



@app.route('/api/screen-flags/<int:screen_id>', methods=['GET'])
def get_screen_flags(screen_id):
    conn = sqlite3.connect('db.sqlite')
    c = conn.cursor()
    c.execute('SELECT force_snapshot, force_resync FROM screen_flags WHERE screen_id = ?', (screen_id,))
    row = c.fetchone()
    conn.close()

    if row:
        return jsonify({
            "force_snapshot": bool(row[0]),
            "force_resync": bool(row[1])
        })
    else:
        # No flags set
        return jsonify({
            "force_snapshot": False,
            "force_resync": False
        })


@app.route('/api/clear-snapshot-flag', methods=['POST'])
def clear_snapshot_flag():
    data = request.get_json()
    screen_id = data.get('screen_id')
    if not screen_id:
        return {"error": "Missing screen_id"}, 400

    conn = sqlite3.connect('db.sqlite')
    c = conn.cursor()
    c.execute('UPDATE screen_flags SET force_snapshot=0 WHERE screen_id=?', (screen_id,))
    conn.commit()
    conn.close()
    return {"message": "Snapshot flag cleared"}, 200

@app.route('/api/clear-sync-flag', methods=['POST'])
def clear_sync_flag():
    data = request.get_json()
    screen_id = data.get('screen_id')
    if not screen_id:
        return {"error": "Missing screen_id"}, 400

    conn = sqlite3.connect('db.sqlite')
    c = conn.cursor()
    c.execute('UPDATE screen_flags SET force_resync=0 WHERE screen_id=?', (screen_id,))
    conn.commit()
    conn.close()
    return {"message": "Sync flag cleared"}, 200



@app.route('/api/group-time/<group_id>')
def group_time(group_id):
    import time
    now_ms = int(time.time() * 1000)
    cycle_ms = 60000  # 60 seconds cycle
    position = now_ms % cycle_ms

    return jsonify({"sync_position_ms": position})



@app.route('/player')
def screen_player():
    return send_from_directory('../screen-player', 'index.html')

@app.route('/player/<path:filename>')
def player_static_files(filename):
    return send_from_directory('../screen-player', filename)



@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/api/snapshot', methods=['POST'])
def upload_snapshot():
    screen_id = request.form.get('screen_id')
    file = request.files.get('snapshot')

    if not screen_id or not file:
        return {"error": "Missing screen_id or snapshot file"}, 400

    # Save snapshots in a snapshots folder
    snapshots_dir = os.path.join(app.root_path, 'snapshots')
    os.makedirs(snapshots_dir, exist_ok=True)

    filename = f"screen_{screen_id}_{int(time.time())}.png"
    filepath = os.path.join(snapshots_dir, filename)

    file.save(filepath)

    # Optional: You can save info about snapshots in DB if needed

    return {"message": "Snapshot uploaded"}, 200




@app.route('/api/ping', methods=['POST'])
def api_ping():
    data = request.get_json()
    screen_id = data.get('screen_id')
    if not screen_id:
        return jsonify({'error': 'Missing screen_id'}), 400

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect('db.sqlite')
    c = conn.cursor()

    # Update screen status + last seen
    c.execute("UPDATE screens SET last_seen = ?, status = 'online' WHERE id = ?", (now, screen_id))

    # ✅ Insert a ping log into the pings table
    c.execute("INSERT INTO pings (screen_id, timestamp) VALUES (?, ?)", (screen_id, now))

    conn.commit()
    conn.close()

    print(f"📡 Received ping from screen {screen_id} at {now}")
    return jsonify({'message': 'Ping received ✅'})



from datetime import datetime, timedelta

def mark_offline_screens():
    threshold = datetime.now() - timedelta(minutes=30)  #  minutes threshold
    threshold_str = threshold.strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect('db.sqlite')
    c = conn.cursor()
    c.execute("UPDATE screens SET status = 'offline' WHERE last_seen < ?", (threshold_str,))
    conn.commit()
    conn.close()


@app.route('/snapshots/<path:filename>')
def serve_snapshot(filename):
    return send_from_directory(os.path.join(app.root_path, 'snapshots'), filename)



# at the bottom of app.py or your main file
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

