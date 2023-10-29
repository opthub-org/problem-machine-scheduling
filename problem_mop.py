import json
import os
import os.path
import random
import re
import subprocess
import time
from typing import List, Tuple

from jsonschema import validate

import model_mop

scip_command_file = "command.txt"
lp_file = "test.lp"
sol_file = "test.sol"
file_num = 27  # 初期解読み込み時の検索ファイル数


def load_problem(problem_file):
    with open(problem_file, "r") as f:
        data = f.readlines()
    data = [row.replace("\n", "").split(" ") for row in data]

    return data


def load_sample_sol(n):
    """初期解読み込み，n:初期解の数"""
    sol_list, eval_list = [], []
    table = [i for i in range(file_num)]
    while len(sol_list) < n and table:
        num = table.pop(random.randrange(0, len(table)))
        if not os.path.isfile("Sol/sol_test{}.sol".format(num)):
            print("sol_test{}.sol is not exist".format(num))
            continue
        with open("Sol/sol_test{}.sol".format(num), "r") as f:
            sol_data = f.readlines()
        obj = float("-inf")
        k_d = {}
        for row in sol_data:
            if not row:
                continue
            if "objective value:" in row:
                obj = float(row.strip("\n").split(" ")[-1])
                continue
            if row.startswith("y("):
                sep_row = row.strip("\n").split(" ")
                sep_row = [s for s in sep_row if not s == ""]
                k_d.update(
                    {
                        int(re.findall(r",(.*)\)", sep_row[0])[0]): int(
                            re.findall(r"\((.*),", sep_row[0])[0]
                        )
                    }
                )
        if obj == float("-inf") or obj >= 75000:
            continue
        sol_list.append(
            [d[1] for d in sorted(k_d.items(), key=lambda x: x[0]) if d[0] > 36]
        )
        eval_list.append(obj)

    return sol_list, eval_list


def evaluation(
        solution: List[int],
        weights: List[float],
        timeout: int,
        problem_file: str,
        jig_file: str
) -> Tuple[List[float], float]:
    """SCIPを起動して評価値を計算する。

    Parameters
    ----------
    solution
        [work1_load, work1_unload, work2_load, ...]
    weights
        [w_1, w_2, w_3, w_4]
    timeout
        Time limit for SCIP
    problem_file
        path/to/problem_file
    jig_file
        path/to/jig_file

    Returns
    -------
    obj : float
        Objective function value.
    const : List[float]
        Constraint values.
    exe_time : float
        Execution time of SCIP.
    """
    model_mop.write_lp(solution, weights, lp_file, problem_file, jig_file)
    with open(scip_command_file, "w") as f:
        f.write(f"read {lp_file}\n")
        f.write(f"set limits time {timeout}\n")
        f.write("optimize\n")
        f.write("display solution\n")
        f.write(f"write solution {sol_file}\n")
        f.write("quit")

    time_s = time.perf_counter()
    subprocess.run(
        f"scip -l Log/Log{int(time.time())}.log -b {scip_command_file}",
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time_e = time.perf_counter()
    exe_time = time_e - time_s

    with open(problem_file, "r") as f:
        problem = f.readlines()
        problem = [row.split() for row in problem]

    margin, xi, psiP, zP = 0.0, 0.0, 0.0, 0.0

    if os.path.isfile(sol_file):
        with open(sol_file, "r") as f:
            data = f.readlines()
        tf_sum = 0.0  # 各ワークの納品時刻の合計値
        tfs = []  # 各ワークの納品時刻変数名リスト
        dead_sum = 0  # 納期の合計値
        count = 0
        for row in problem[1:]:
            count += int(len(row) / 7) * 3
            tfs.append(f"tf{count}")
            dead_sum += int(row[-1]) * 1440 - 960
        for row in data:
            if row == "":
                continue
            # 以下重み無し，項別目的関数値
            # 各ワークの納品時刻を取得
            if "tf" in row:
                val = row.split()
                if val[0] in tfs:
                    tf_sum += float(val[-2])
            # メイクスパンを取得（第2項）
            if "xi" in row:
                val = row.split()
                xi = float(val[-2])
            # 納期遅れ量の総和を取得（第3項）
            if "psiP" in row:
                val = row.split()
                if len(val[0]) == 4:
                    psiP = float(val[-2])
            # 残業時間の総和を取得（第4項）
            if "zP" in row:
                val = row.split()
                if len(val[0]) == 2:
                    zP = float(val[-2])
        margin = dead_sum - tf_sum  # 納期余裕和（第1項）
        os.remove(sol_file)

    return [-margin, xi, psiP, zP], exe_time


def load_val_json(json_str: str, n_work: int, max_date: int = 9) -> Tuple[List[int], List[float], int]:
    """JSON文字列を脱直列化し，データを検証する．

    Parameters
    ----------
    json_str : str
    '{
        "schedule": int[n_works] (1 <= work_date <= MAX_DATE) n_works = sum_i work_iの取付・取外の回数
        "weights": float[4], (0 <= x <= 1)
        "timeout": int (60 <= x <= 8 * 60 * 60)
    }'
    n_work : int
        n_works = sum_i work_i
    max_date: int , 9
        Maximum date for schedule

    Returns
    -------
    schedule : List[int]
        Schedule (design variables).
    weights : List[float]
        Weights for scalarizing objectives
    timeout : int
        Time limit for SCIP
    """
    schedule_len = n_work
    schedule_min = 1
    schedule_max = max_date
    weights_len = 4
    weights_min = 0
    weights_max = 1
    time_min = 5 * 60
    time_max = 8 * 60 * 60
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "input schema",
        "type": "object",
        "properties": {
            "schedule": {
                "type": "array",
                "minItems": schedule_len,
                "maxItems": schedule_len,
                "items": {
                    "type": "integer",
                    "minimum": schedule_min,
                    "maximum": schedule_max
                }
            },
            "weights": {
                "type": "array",
                "minItems": weights_len,
                "maxItems": weights_len,
                "items": {
                    "type": "number",
                    "minimum": weights_min,
                    "maximum": weights_max
                }
            },
            "timeout": {
                "type": "integer",
                "minimum": time_min,
                "maximum": time_max
            }
        },
        "additionalProperties": False,
        "required": ["schedule", "weights", "timeout"]
    }

    data = json.loads(json_str)
    validate(data, schema)

    return data["schedule"], data["weights"], data["timeout"]


def get_problem_paths(default_problem: str = "work_test.txt", default_jig: str = "jig_origin.csv") -> Tuple[str, str]:
    problem = os.getenv("PROBLEM")
    if problem is None:
        return default_problem, default_jig

    problem_path = f"problems/{problem}/work_{problem}.txt"
    jig_path = f"problems/{problem}/jig_{problem}.csv"

    return problem_path, jig_path


def get_n_work(problem_file: str) -> int:
    with open(problem_file, "r") as f:
        problem = f.readlines()
    problem = [row.replace("\n", "").split(" ") for row in problem]
    process_num = sum([int(len(n) / 7) for n in problem[13:]])  # 加工回数（scheduleの配列長）

    return process_num


def get_max_date(default_max: int = 9) -> int:
    return int(os.getenv("MAX_DATE", default_max))


def main():
    problem_file, jig_file = get_problem_paths()
    n_work = get_n_work(problem_file)
    max_date = get_max_date()
    str_json = input()
    # ここでフォーマットの検証などをjsonschemaでやる
    schedule, weights, timeout = load_val_json(str_json, n_work, max_date)

    objs, exe_time = evaluation(schedule, weights, timeout, problem_file, jig_file)
    json_out = json.dumps({
        "objective": objs,
        "constraint": None,
        "error": None,
        "info": {
            "exe_time": exe_time
        }
    })
    print(json_out)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        out_json = json.dumps(
            {"objective": None, "constraint": None, "info": None, "error": str(e)}
        )
        print(out_json)
