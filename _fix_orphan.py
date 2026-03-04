with open('agent_dashboard.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find where the orphan starts (after the last </section> for global-agent)
# and where VIEW 2 starts
start_idx = None
end_idx = None

for i, line in enumerate(lines):
    if start_idx is None and '            <div class="agent-cell">' in line and i > 800:
        start_idx = i
    if '<!-- VIEW 2: AGENT DETAIL' in line:
        end_idx = i
        break

print(f"start_idx={start_idx}, end_idx={end_idx}")
if start_idx and end_idx:
    # Keep everything up to (not including) start_idx, then from end_idx onward
    new_lines = lines[:start_idx] + lines[end_idx:]
    with open('agent_dashboard.html', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print(f"Removed lines {start_idx} to {end_idx-1} ({end_idx-start_idx} lines)")
    print(f"New line count: {len(new_lines)}")
else:
    print("Could not find markers! Manual inspection required.")
    # Print context around line 815
    for i, l in enumerate(lines[810:830], start=811):
        print(f"{i}: {repr(l)}")
