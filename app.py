from flask import Flask, render_template, jsonify

app = Flask(__name__)

# Variable to track the number of treats left
treats_left = 5

@app.route('/')
def home():
    return render_template('index.html', treats=treats_left)

@app.route('/give_treat', methods=['POST'])
def give_treat():
    global treats_left
    if treats_left > 0:
        treats_left -= 1
        message = "Apollo got a treat!"
    else:
        message = "No more treats left for today!"

    bones = '🍖 ' * treats_left  # Display the remaining treats as dog bone emojis

    return jsonify({'treats_left': bones.strip(), 'message': message})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
