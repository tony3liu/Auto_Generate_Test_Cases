import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from models.test_case import TestCase
from schemas.communication import TestScenario

class TestCaseGenerator:
    def __init__(self, template_path: Optional[str] = None):
        self.template_path = template_path
        self.base_template = self._load_template() if template_path else {}

    def _load_template(self) -> Dict:
        """加载测试用例模板配置"""
        if self.template_path is None:
            return {}
        try:
            with open(file=self.template_path, mode='r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

    def generate_test_cases(self, test_strategy: Dict[str, Any]) -> List[TestCase]:
        """基于测试策略生成测试用例
        
        Args:
            test_strategy: 包含测试策略的字典，应包含以下字段：
                - scenarios: 测试场景列表
                - test_types: 测试类型配置
                - priorities: 优先级定义
                - validation_rules: 验证规则
        
        Returns:
            List[TestCase]: 生成的测试用例列表
        """
        test_cases = []
        scenarios = test_strategy.get('scenarios', [])
        test_types = test_strategy.get('test_types', {})
        priorities = test_strategy.get('priorities', {})
        validation_rules = test_strategy.get('validation_rules', {})

        for scenario in scenarios:
            # 根据场景类型生成对应的测试用例
            scenario_type = scenario.get('type')
            if scenario_type in test_types:
                test_case = self._create_test_case(
                    scenario=scenario,
                    test_type=test_types[scenario_type],
                    priorities=priorities,
                    validation_rules=validation_rules
                )
                if test_case:
                    test_cases.append(test_case)

        return test_cases

    def _create_test_case(self, 
                         scenario: Dict[str, Any],
                         test_type: Dict[str, Any],
                         priorities: Dict[str, Any],
                         validation_rules: Dict[str, Any]) -> Optional[TestCase]:
        """创建单个测试用例
        
        Args:
            scenario: 测试场景信息
            test_type: 测试类型配置
            priorities: 优先级定义
            validation_rules: 验证规则
        
        Returns:
            Optional[TestCase]: 生成的测试用例，如果生成失败则返回None
        """
        try:
            # 获取测试用例基本信息
            title = f"{test_type.get('name', '')} - {scenario.get('description', '')}"
            priority = self._determine_priority(scenario, priorities)
            category = test_type.get('category', '功能测试')

            # 生成测试步骤和预期结果
            steps = self._generate_steps(test_type, scenario)
            expected_results = self._generate_expected_results(test_type, scenario, validation_rules)

            # 创建测试用例
            test_case = TestCase(
                title=title,
                description=scenario.get('description', ''),
                preconditions=scenario.get('preconditions', []),
                steps=steps,
                expected_results=expected_results,
                priority=priority,
                category=category
            )

            # 添加额外的测试数据
            test_case.test_data = self._generate_test_data(test_type, scenario)
            
            return test_case
        except Exception as e:
            print(f"创建测试用例失败: {str(e)}")
            return None

    def _determine_priority(self, scenario: Dict[str, Any], priorities: Dict[str, Any]) -> str:
        """根据场景和优先级定义确定测试用例优先级"""
        scenario_priority = scenario.get('priority')
        if scenario_priority in priorities:
            return priorities[scenario_priority].get('level', '中')
        return '中'

    def _generate_steps(self, test_type: Dict[str, Any], scenario: Dict[str, Any]) -> List[str]:
        """生成测试步骤"""
        base_steps = test_type.get('base_steps', [])
        scenario_steps = scenario.get('steps', [])
        return base_steps + scenario_steps

    def _generate_expected_results(self, 
                                 test_type: Dict[str, Any], 
                                 scenario: Dict[str, Any],
                                 validation_rules: Dict[str, Any]) -> List[str]:
        """生成预期结果"""
        base_results = test_type.get('base_expected_results', [])
        scenario_results = scenario.get('expected_results', [])
        
        # 添加验证规则相关的预期结果
        if validation_rules:
            rule_results = self._generate_validation_rule_results(test_type, validation_rules)
            return base_results + scenario_results + rule_results
        
        return base_results + scenario_results

    def _generate_validation_rule_results(self, 
                                        test_type: Dict[str, Any],
                                        validation_rules: Dict[str, Any]) -> List[str]:
        """根据验证规则生成预期结果"""
        results = []
        type_rules = validation_rules.get(test_type.get('name', ''), {})
        
        for rule_name, rule_value in type_rules.items():
            if isinstance(rule_value, dict):
                threshold = rule_value.get('threshold')
                if threshold is not None:
                    results.append(f"{rule_name}应达到{threshold}")
            elif isinstance(rule_value, (int, float)):
                results.append(f"{rule_name}应达到{rule_value}")
        
        return results

    def _generate_test_data(self, test_type: Dict[str, Any], scenario: Dict[str, Any]) -> Dict[str, Any]:
        """生成测试数据"""
        test_data = {}
        
        # 合并测试类型的基础数据和场景特定数据
        base_data = test_type.get('test_data', {})
        scenario_data = scenario.get('test_data', {})
        
        test_data.update(base_data)
        test_data.update(scenario_data)
        
        return test_data