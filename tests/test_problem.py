import unittest
import json
from jsonschema import ValidationError

from problem import load_val_json


class TestLoadValJSON(unittest.TestCase):
    def test_normal_load(self):
        """
        JSON文字列を正常に脱直列化し，設計変数，時間変数それぞれに対応する2値を返す．
        """
        json_str = '{"schedule": [1, 2, 3, 4], "timeout": 500}'

        schedule_out, time_out = load_val_json(json_str, 2)

        self.assertEqual([1, 2, 3, 4], schedule_out)
        self.assertEqual(500, time_out)

    def test_normal_time_range(self):
        """
        時間変数のとりうる範囲：5*60秒以上、8*60*60秒以下
        """
        times = [h * 60 * 60 for h in range(1, 9)]
        times.insert(0, 5 * 60)
        for t in times:
            json_str = '{"schedule": [1, 2, 3, 4], "timeout": %d}' % t
            with self.subTest(timeout=t):
                try:
                    load_val_json(json_str, 2)
                except ValidationError:
                    self.fail("Unexpected Exception on Validation")

    def test_normal_schedule_len(self):
        """
        設計変数の数：ワークの総加工数の2倍（取付、取外）
        """
        num_works = list(range(0, 31, 5))
        num_works[0] = 1
        for n in num_works:
            schedule = [5 for _ in range(2 * n)]
            data = dict(schedule=schedule, timeout=500)
            json_str = json.dumps(data)
            with self.subTest(num_work=n):
                try:
                    schedule_out, _ = load_val_json(json_str, n)
                except ValidationError:
                    self.fail("Unexpected Exception on Validation")

                self.assertEqual(len(schedule_out), 2 * n)

    def test_normal_schedule_range(self):
        """
        各変数のとりうる値：1以上、9以下の整数（境界値を含む）
        """
        for load in range(1, 10):
            schedule = [load for _ in range(4)]
            data = dict(schedule=schedule, timeout=500)
            json_str = json.dumps(data)
            with self.subTest(load=load):
                try:
                    schedule_out, _ = load_val_json(json_str, 2)
                except ValidationError:
                    self.fail("Unexpected Exception on Validation")

    def test_error_time_range(self):
        """
        時間変数のとりうる範囲：5*60秒以上、8*60*60秒以下
        """
        times = [1, 5 * 60 - 1, 8 * 60 * 60 + 1, 9 * 60 * 60]
        for t in times:
            json_str = '{"schedule": [1, 2, 3, 4], "timeout": %d}' % t
            with self.subTest(time=t), self.assertRaises(ValidationError):
                load_val_json(json_str, 2)

    def test_error_time_type(self):
        """
        時間変数は整数で与えられる．
        """
        json_str = '{"schedule": [1, 2, 3, 4], "timeout": 500.1}'
        with self.subTest(type=float), self.assertRaises(ValidationError):
            load_val_json(json_str, 2)

        json_str = '{"schedule": [1, 2, 3, 4], "timeout": "500"}'
        with self.subTest(type=str), self.assertRaises(ValidationError):
            load_val_json(json_str, 2)

    def test_error_schedule_len(self):
        """
        設計変数の数：ワークの総加工数の2倍（取付、取外）
        """
        for mul in [0, 1, 3]:
            schedule = [5 for _ in range(mul * 2)]
            data = dict(schedule=schedule, timeout=500)
            json_str = json.dumps(data)
            with self.subTest(mul=mul), self.assertRaises(ValidationError):
                load_val_json(json_str, 2)

    def test_error_schedule_rage(self):
        """
        各変数のとりうる値：1以上、9以下の整数（境界値を含む）
        """
        for load in [0, 10]:
            schedule = [load for _ in range(4)]
            data = dict(schedule=schedule, timeout=500)
            json_str = json.dumps(data)
            with self.subTest(load=load), self.assertRaises(ValidationError):
                load_val_json(json_str, 2)

    def test_error_schedule_type(self):
        """
        設計変数は整数のリストで与えられる．
        """
        json_str = '{"schedule": "[1, 2, 3, 4]", "timeout": 500}'
        with self.subTest(type="str"), self.assertRaises(ValidationError):
            load_val_json(json_str, 2)

        json_str = '{"schedule": [1.1, 2.1, 3.1, 4.1], "timeout": 500}'
        with self.subTest(type="List[float]"), self.assertRaises(ValidationError):
            load_val_json(json_str, 2)

        json_str = '{"schedule": ["1", "2", "3", "4"], "timeout": 500}'
        with self.subTest(type="List[str]"), self.assertRaises(ValidationError):
            load_val_json(json_str, 2)

        json_str = '{"schedule": [1, "2", 3.1, 4], "timeout": 500}'
        with self.subTest(type="List"), self.assertRaises(ValidationError):
            load_val_json(json_str, 2)

    def test_error_extra_property(self):
        """
        関係ないプロパティは許容しない
        """
        json_str = '{"schedule": [1, 2, 3, 4], "timeout": 500, "favorite": "ramen"}'

        with self.assertRaises(ValidationError):
            load_val_json(json_str, 2)

    def test_error_lack_property(self):
        """
        "schedule"と"timeout"は必須．
        """
        json_str = '{"timeout": 500}'
        with self.subTest(prop="schedule"), self.assertRaises(ValidationError):
            load_val_json(json_str, 2)

        json_str = '{"schedule": [1, 2, 3, 4]}'
        with self.subTest(prop="timeout"), self.assertRaises(ValidationError):
            load_val_json(json_str, 2)


if __name__ == '__main__':
    unittest.main()
