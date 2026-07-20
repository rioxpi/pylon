METADATA = {
    "trigger" : "ls"
}

app = None

def initialize(network):
    global app
    app = network

def execute():
    data = app.execute_command("ls", 1)
    return data

def parse_data(data) -> str:
    return "test1, test2, test3"