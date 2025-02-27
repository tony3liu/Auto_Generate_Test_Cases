# src/agents/quality_assurance.py
import os
import autogen
from typing import Dict, List
import logging
from dotenv import load_dotenv
from src.utils.agent_io import AgentIO
load_dotenv()
logger = logging.getLogger(__name__)

# 使用 Azure OpenAI 配置
api_key = os.getenv("AZURE_OPENAI_API_KEY")
base_url = os.getenv("AZURE_OPENAI_BASE_URL")
model = os.getenv("AZURE_OPENAI_MODEL")
model_version = os.getenv("AZURE_OPENAI_MODEL_VERSION")

class QualityAssuranceAgent:
    def __init__(self):
        self.config_list = [
            {
                "model": model,
                "api_key": api_key,
                "base_url": base_url,
                "api_type": "azure",
                "api_version": model_version
            }
        ]
        
        # 初始化AgentIO用于保存和加载审查结果
        self.agent_io = AgentIO()
        
        # 初始化agent
        self.agent = autogen.AssistantAgent(
            name="quality_assurance",
            system_message="""你是一位专业的质量保证工程师，负责审查和改进测试用例。
            你的职责是确保测试用例的完整性、清晰度、可执行性，并关注边界情况和错误场景。
            
            在审查测试用例时，请重点关注以下方面：
            1. 完整性：确保测试用例包含所有必要的字段和信息
            2. 清晰度：确保测试步骤和预期结果描述清晰明确
            3. 可执行性：确保测试用例可以被执行和验证
            4. 边界情况：检查是否考虑了各种边界条件
            5. 错误场景：验证是否包含了必要的错误处理场景
            
            请提供具体的改进建议，包括但不限于：
            - 缺失字段的补充建议
            - 不清晰描述的改进方案
            - 可执行性的增强建议
            - 边界条件的补充建议
            - 错误场景的完善建议""",
            llm_config={"config_list": self.config_list}
        )
        
        # 添加last_review属性，用于跟踪最近的审查结果
        self.last_review = None
        
        # 尝试加载之前的审查结果
        self._load_last_review()

    def _load_last_review(self):
        """加载之前保存的审查结果"""
        try:
            result = self.agent_io.load_result("quality_assurance")
            if result:
                self.last_review = result
                logger.info("成功加载之前的质量审查结果")
        except Exception as e:
            logger.error(f"加载质量审查结果时出错: {str(e)}")
    
    def review(self, test_cases: List[Dict]) -> List[Dict]:
        """审查和改进测试用例。"""
        try:
            user_proxy = autogen.UserProxyAgent(
                name="user_proxy",
                system_message="测试用例提供者",
                human_input_mode="NEVER",
                code_execution_config={"use_docker": False}
            )

            # 审查测试用例
            user_proxy.initiate_chat(
                self.agent,
                message=f"""请审查以下测试用例并提供改进建议：
                
                测试用例: {test_cases}
                
                检查以下方面：
                1. 完整性
                2. 清晰度
                3. 可执行性
                4. 边界情况
                5. 错误场景""",
                max_turns=1  # 限制对话轮次为1，避免死循环
            )

            reviewed_cases = self._process_review(test_cases, self.agent.last_message())
            
            # 如果审查结果为空，返回原始测试用例
            if not reviewed_cases:
                logger.warning("测试用例审查结果为空，返回原始测试用例")
                return test_cases
            
            # 保存审查结果到last_review属性
            self.last_review = reviewed_cases
            logger.info(f"测试用例审查完成，共审查 {len(reviewed_cases)} 个测试用例")
            
            # 将审查结果保存到文件
            self.agent_io.save_result("quality_assurance", reviewed_cases)
            
            return reviewed_cases

        except Exception as e:
            logger.error(f"测试用例审查错误: {str(e)}")
            raise

    def _process_review(self, original_cases: List[Dict], review_feedback) -> List[Dict]:
        """处理审查反馈并更新测试用例。"""
        reviewed_cases = []
        for case in original_cases:
            improved_case = self._improve_test_case(case, review_feedback)
            reviewed_cases.append(improved_case)
        return reviewed_cases

    def _improve_test_case(self, test_case: Dict, feedback) -> Dict:
        """根据反馈改进测试用例。"""
        try:
            if not test_case:
                logger.warning("测试用例为空")
                return test_case
                
            if not feedback:
                logger.warning("反馈为空")
                return test_case

            # 创建改进后的测试用例副本
            improved_case = test_case.copy()
            
            # 检查feedback类型
            if isinstance(feedback, dict):
                # 如果是字典类型，尝试从content字段获取内容
                if 'content' in feedback:
                    feedback = feedback['content']
                else:
                    logger.error(f"无法从字典中提取反馈内容: {feedback}")
                    return test_case
            
            # 确保feedback是字符串类型
            if not isinstance(feedback, str):
                logger.error(f"反馈不是字符串类型: {type(feedback)}")
                return test_case
                
            # 解析反馈内容
            feedback_sections = [line.strip() for line in feedback.split('\n') if line.strip()]
            current_section = None
            improvements = {
                'completeness': [],
                'clarity': [],
                'executability': [],
                'boundary_cases': [],
                'error_scenarios': []
            }
            
            # 提取各个方面的改进建议
            for line in feedback_sections:
                # 识别章节标题
                section_mapping = {
                    '1. 完整性': 'completeness',
                    '2. 清晰度': 'clarity',
                    '3. 可执行性': 'executability',
                    '4. 边界情况': 'boundary_cases',
                    '5. 错误场景': 'error_scenarios'
                }
                
                for title, section in section_mapping.items():
                    if title in line:
                        current_section = section
                        break
                
                # 提取建议内容
                if current_section and (line.startswith('-') or line.startswith('•')):
                    content = line[1:].strip()
                    if content:  # 确保内容不为空
                        improvements[current_section].append(content)
            
            # 根据反馈改进测试用例
            # 完整性改进
            if improvements['completeness']:
                required_fields = ['preconditions', 'steps', 'expected_results']
                for field in required_fields:
                    if field not in improved_case:
                        improved_case[field] = []
                    elif not isinstance(improved_case[field], list):
                        improved_case[field] = [improved_case[field]]
            
            # 清晰度改进
            if improvements['clarity']:
                # 确保标题清晰明确
                if 'title' in improved_case:
                    improved_case['title'] = improved_case['title'].strip() if improved_case['title'] else ''
                # 确保步骤描述清晰
                if 'steps' in improved_case:
                    improved_case['steps'] = [step.strip() for step in improved_case['steps'] if step]
            
            # 可执行性改进
            if improvements['executability']:
                steps = improved_case.get('steps', [])
                results = improved_case.get('expected_results', [])
                if steps:
                    # 确保每个步骤都有对应的预期结果
                    if len(steps) > len(results):
                        results.extend(['待补充'] * (len(steps) - len(results)))
                    improved_case['expected_results'] = results
            
            # 边界情况改进
            if improvements['boundary_cases']:
                boundary_conditions = improved_case.setdefault('boundary_conditions', [])
                # 去重并添加新的边界条件
                new_conditions = [cond for cond in improvements['boundary_cases'] 
                                if cond not in boundary_conditions]
                boundary_conditions.extend(new_conditions)
            
            # 错误场景改进
            if improvements['error_scenarios']:
                error_scenarios = improved_case.setdefault('error_scenarios', [])
                # 去重并添加新的错误场景
                new_scenarios = [scenario for scenario in improvements['error_scenarios'] 
                               if scenario not in error_scenarios]
                error_scenarios.extend(new_scenarios)
            
            # 验证改进后的测试用例
            if not self._validate_improvements(test_case, improved_case):
                logger.warning(f"测试用例改进可能导致数据丢失: {test_case.get('id', 'unknown')}")
                return test_case
            
            return improved_case
            
        except Exception as e:
            logger.error(f"改进测试用例错误: {str(e)}")
            return test_case

    def _validate_improvements(self, original: Dict, improved: Dict) -> bool:
        """验证改进是否保持测试用例的完整性。"""
        return all(key in improved for key in original.keys())