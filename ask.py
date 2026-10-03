def ask_user():
    user_input = input("What is the Answer to the Great Question of Life, the Universe, and Everything?")
    if user_input.strip() == "42":
        print("Correct!")
    elif user_input.strip().lower() == "forty-two" or user_input.strip().lower() == "forty two":
        print("Correct!")
    else:
        print("Incorrect")

ask_user()