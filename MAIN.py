import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import math, numpy as np, random, threading
import socket, cv2
from flask import Flask, request, Response


# Sensitivity for mouse movement
S = 0.005

# Camera vectors
camPos = np.array([0, 0, 0], np.float64)
camR = np.array([1, 0, 0], np.float64)
camU = np.array([0, 1, 0], np.float64)
camF = np.array([0, 0, 1], np.float64)
yaw = 0

# Sample DNS data and their 3D positions
MAX_DNS=20
DISTANCE=50
DNS = ["example.com"]
DNS_POS = [np.array([random.random()*DISTANCE, random.random()*DISTANCE, random.random()*DISTANCE]) for _ in range(MAX_DNS)]

# Listen for UDP packets and update DNS list
def sniffer():
    global MAX_DNS
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("0.0.0.0", 8989))
    while True:
        data, addr = s.recvfrom(1024)
        DNS.append(data.decode())
        if len(DNS) >= MAX_DNS:
            s.close()
            break
threading.Thread(target=sniffer).start()

# Apply X/Y axis rotation to a vector
def rotate(vector, angle_x, angle_y):
    x, y, z = vector
    y1 = y * math.cos(angle_x) - z * math.sin(angle_x)
    z1 = y * math.sin(angle_x) + z * math.cos(angle_x)
    x1 = x
    x2 = x1 * math.cos(angle_y) + z1 * math.sin(angle_y)
    z2 = -x1 * math.sin(angle_y) + z1 * math.cos(angle_y)
    y2 = y1
    vector[0], vector[1], vector[2] = (x2, y2, z2)

# Flask application setup
app = Flask(__name__)

@app.route("/key", methods=["POST"])
def key():
    global camPos, camR, camF
    json = request.get_json()
    f = json.get("f") or 0
    r = json.get("r") or 0
    print(f"MOVE: {f} + {-r}")
    camPos += f * camF - r * camR
    return "ok"

@app.route("/mouse", methods=["POST"])
def mouse():
    global yaw, camU, camR, camF, S
    json = request.get_json()
    dx = float(json.get("x") or 0) * S
    dy = float(json.get("y") or 0) * S
    print(dx, dy)
    yaw += dy
    if yaw >= math.pi / 2 or yaw <= -math.pi / 2:
        dy = 0
    rotate(camR, dy, -dx)
    rotate(camU, dy, -dx)
    rotate(camF, dy, -dx)
    return "ok"

@app.route("/upload", methods=["GET"])
def upload():
    return Response(generate_current_frame(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/", methods=["GET"])
def get():
    with open("index.html", "r") as f:
        return f.read()

# Launch the Flask app in a thread
def runner():
    app.run(host="0.0.0.0", port=7878)
threading.Thread(target=runner, daemon=True).start()

# Stream OpenGL frames as MJPEG
def generate_current_frame():
    global DNS, DNS_POS, camPos, camU, camR, camF, clock

    def init_renderer():
        global DISPLAY, clock
        pygame.init()
        DISPLAY = (800, 600)
        pygame.display.set_mode(DISPLAY, OPENGL | DOUBLEBUF)
        clock = pygame.time.Clock()
        glEnable(GL_DEPTH_TEST)
        glMatrixMode(GL_PROJECTION)
        gluPerspective(75, DISPLAY[0]/DISPLAY[1], 0.1, 100.0)
        glMatrixMode(GL_MODELVIEW)
        glClearColor(0.3, 0.3, 0.3, 1.0)  # R, G, B, A from 0.0 to 1.0

    init_renderer()

    # Render text to a texture for OpenGL
    def make_text_texture(text, font_size=32):
        font = pygame.font.SysFont("Arial", font_size)
        surface = font.render(text, True, (255, 255, 255), (0, 0, 0))
        texture_data = pygame.image.tostring(surface, "RGBA", True)
        width, height = surface.get_size()

        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        return tex_id, width, height

    # Draw the given text at a 3D location
    def draw_text_3d(x, y, z, text, size=32, scale=0.01):
        tex_id, w, h = make_text_texture(text, size)
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glColor3f(1, 1, 1)
        glPushMatrix()
        glTranslatef(x, y, z)
        glScalef(w * scale, h * scale, 1)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex3f(0, 0, 0)
        glTexCoord2f(1, 0); glVertex3f(1, 0, 0)
        glTexCoord2f(1, 1); glVertex3f(1, 1, 0)
        glTexCoord2f(0, 1); glVertex3f(0, 1, 0)
        glEnd()
        glPopMatrix()
        glDeleteTextures([tex_id])
        glDisable(GL_TEXTURE_2D)

    # Capture current OpenGL frame as JPEG
    def create_buffer(width=DISPLAY[0], height=DISPLAY[1]):
        pixels = glReadPixels(0, 0, width, height, GL_RGB, GL_UNSIGNED_BYTE)
        surface = pygame.image.fromstring(pixels, (width, height), "RGB")
        surface = pygame.transform.flip(surface, False, True)
        arr = pygame.surfarray.array3d(surface)
        arr = np.transpose(arr, (1, 0, 2))
        ret, jpeg = cv2.imencode('.jpg', arr)
        return jpeg.tobytes()

    # Draw a colored triangle
    def draw_triangle():
        glBegin(GL_TRIANGLES)
        glColor3f(1.0, 0.0, 0.0); glVertex3f(-0.5, -0.5, 0)
        glColor3f(0.0, 1.0, 0.0); glVertex3f(0.5, -0.5, 0)
        glColor3f(0.0, 0.0, 1.0); glVertex3f(0.0, 0.5, 0)
        glEnd()

    TRIG_CENTRE = np.array([0, 0, 0], np.float64)
    AUI = np.array([0.1, 0.1, 0.1], np.float64)

    while True:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                break

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        gluLookAt(*camPos, *(camPos + camF), *camU)

        draw_triangle()

        for dns in range(len(DNS)):
            draw_text_3d(*DNS_POS[dns], DNS[dns])
            glBegin(GL_TRIANGLES)
            glVertex3f(*(TRIG_CENTRE + 0.5 * AUI))
            glVertex3f(*(TRIG_CENTRE - 0.5 * AUI))
            glVertex3f(*DNS_POS[dns])
            glEnd()

        buffer = create_buffer()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer + b'\r\n')
        pygame.display.flip()
        clock.tick(20)