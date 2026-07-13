import unittest

from task_contract import (
    MAPPING_VERSION,
    Operation,
    WarehouseTask,
    map_logical_to_physical,
)


class MappingTests(unittest.TestCase):
    def test_four_corners_map_to_nine_by_six_corners(self):
        self.assertEqual(map_logical_to_physical(0), 1)
        self.assertEqual(map_logical_to_physical(19), 9)
        self.assertEqual(map_logical_to_physical(380), 46)
        self.assertEqual(map_logical_to_physical(399), 54)

    def test_mapping_is_monotonic_on_each_axis(self):
        bottom = [map_logical_to_physical(col) for col in range(20)]
        left = [map_logical_to_physical(tier * 20) for tier in range(20)]
        self.assertEqual(bottom, sorted(bottom))
        self.assertEqual(left, sorted(left))

    def test_mapping_rejects_out_of_range_logical_cell(self):
        for invalid in (-1, 400):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    map_logical_to_physical(invalid)


class WarehouseTaskTests(unittest.TestCase):
    def test_operation_requires_the_correct_cells(self):
        WarehouseTask(1, 1, Operation.INBOUND, 7, logical_target=399)
        WarehouseTask(2, 2, Operation.OUTBOUND, 7, logical_source=0)
        WarehouseTask(
            3, 3, Operation.DUAL, 7,
            logical_source=0, logical_target=399,
        )
        with self.assertRaises(ValueError):
            WarehouseTask(4, 4, Operation.INBOUND, 7)
        with self.assertRaises(ValueError):
            WarehouseTask(5, 5, Operation.OUTBOUND, 7)

    def test_physical_cells_are_derived_not_supplied(self):
        task = WarehouseTask(
            9, 12, Operation.DUAL, 88,
            logical_source=0, logical_target=399,
            strategy_id=3, reason_code=17,
        )
        self.assertEqual(task.physical_source, 1)
        self.assertEqual(task.physical_target, 54)
        self.assertEqual(task.mapping_version, MAPPING_VERSION)

    def test_round_trip_preserves_contract(self):
        task = WarehouseTask(
            9, 12, Operation.DUAL, 88,
            logical_source=21, logical_target=378,
            strategy_id=3, reason_code=17,
        )
        self.assertEqual(WarehouseTask.from_dict(task.to_dict()), task)

    def test_ids_must_be_positive(self):
        with self.assertRaises(ValueError):
            WarehouseTask(0, 1, Operation.INBOUND, 1, logical_target=1)
        with self.assertRaises(ValueError):
            WarehouseTask(1, 0, Operation.INBOUND, 1, logical_target=1)


if __name__ == "__main__":
    unittest.main()
