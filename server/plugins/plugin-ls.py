import re

METADATA = {
    "trigger" : "ls"
}

app = None

def initialize(network):
    global app
    app = network

def execute():
    data = app.execute_command("ls -l", 1)
    return parse_data(data)

def parse_data(data : str) -> str:
    pattern = r'^\s*(?P<perms>[\w-]{10}[+@]?)\s+(?P<links>\d+)\s+(?P<owner>\S+)\s+(?P<group>\S+)\s+(?P<size>\d+)\s+(?P<date>\w{3}\s+\d+\s+[\d:]+)\s+(?P<name>.+?)(?:\s+->\s+(?P<target>.+))?$'
    out = []
    lines = data.splitlines()
    for d in lines:
        cleaned_line = d.strip()
        match = re.match(pattern, cleaned_line)
        if match:
            out.append(match.groupdict())
    
    out_string = convert_to_string(out)
    
    return out_string

def convert_to_string(parsed_data: list) -> str:
    header = f"{'PERMISSIONS':<13} {'OWNER':<12} {'GROUP':<12} {'SIZE (B)':<12} {'MODIFICATION DATE ':<17} {'NAME'}"
    out = ""
    
    out += f"\n{header}\n"
    out += ('-' * len(header))

    for item in parsed_data:
        name = item['name']
        if item.get('target'):
            name = f"{name} -> {item['target']}"

        out += f"\n{item['perms']:<13} " f"{item['owner']:<12} " f"{item['group']:<12} " f"{item['size']:>11}  " f"{item['date']:<17} " f"{name}"  
    
    return out