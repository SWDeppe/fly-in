from fly_in.cbs.astar import TimedPath


def log_output(out_path: str, paths: list[TimedPath]) -> None:
    with open(out_path, 'w+') as f:
        t = 0
        while True:
            line = ""
            for id, path in enumerate(paths):
                if t >= path.arrival_time:
                    continue
                step = path.step_t(t)
                if step.source == step.target and step.duration == 1:
                    continue
                line += f"D{id}-{step.target} "
            if line == "":
                break
            f.write(line[:-1] + "\n")
            t += 1
