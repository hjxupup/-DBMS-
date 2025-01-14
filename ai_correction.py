import re
from typing import Dict, List, Tuple
import difflib

class SQLCorrector:
    def __init__(self):
        # SQL 语法模板
        self.sql_templates = {
            'select': {
                'simple': "SELECT {columns} FROM {table}",
                'where': "SELECT {columns} FROM {table} WHERE {conditions}",
                'join': "SELECT {columns} FROM {table1} JOIN {table2} ON {join_condition}",
                'join_where': "SELECT {columns} FROM {table1} JOIN {table2} ON {join_condition} WHERE {conditions}"
            },
            'insert': "INSERT INTO {table} {columns}={values}",
            'delete': "DELETE ON {table} WHERE {conditions}",
            'update': "UPDATE {table} SET {columns} WHERE {conditions}",
            'create_table': "CREATE TABLE {table} ({columns})",
            'drop_table': "DROP TABLE {table}"
        }
        
        # 修改 common_errors 中的模式以支持中文
        self.common_errors = {
            'commands': [
                (r'creat\b', 'create'),
                (r'slect\b', 'select'),
                (r'insrt\b', 'insert'),
                (r'delte\b', 'delete'),
                (r'updte\b', 'update'),
                (r'databse\b', 'database'),
                (r'tabel\b', 'table'),
                (r'wher\b', 'where'),
                (r'fom\b', 'from'),
                (r'jion\b', 'join'),
            ],
            'operators': [
                (r'\s*=\s*', '='),
                (r'\s*>\s*', '>'),
                (r'\s*<\s*', '<'),
                (r'\s*,\s*', ','),
            ],
            'structure': [
                (r'create\s+(\w+)\s*\(', 'create table \\1 ('),
                (r'select\s+from', 'select * from'),
                (r'join\s+(\w+)\s+(\w+)', 'join \\1 on \\2'),
            ]
        }
        
        # 添加智能提示模板
        self.command_templates = {
            'create': {
                'database': 'create database database_name',
                'table': 'create table table_name (column1 type, column2 type)',
                'view': 'create view view_name as select * from table_name'
            },
            'select': {
                'simple': 'select column1, column2 from table_name',
                'where': 'select * from table_name where condition',
                'join': 'select * from table1 join table2 on table1.id = table2.id'
            },
            'insert': 'insert into table_name (column1, column2) values (value1, value2)',
            'delete': 'delete from table_name where condition',
            'update': 'update table_name set column = value where condition'
        }
        
        # 添加性能优化模式
        self.performance_patterns = {
            'join_order': [
                (r'big_table.*join.*small_table', '建议将小表放在左边以优化连接性能'),
            ],
            'index_usage': [
                (r'where\s+(\w+)\s*=', '建议在等值查询列上创建索引'),
                (r'order\s+by\s+(\w+)', '建议在排序列上创建索引'),
            ],
            'group_patterns': [
                (r'group\s+by\s+(\w+)', '建议在分组列上创建索引'),
            ]
        }
        
        # 添加查询复杂度评估规则
        self.complexity_rules = {
            'simple': {'joins': 0, 'conditions': 1},
            'medium': {'joins': 1, 'conditions': 2},
            'complex': {'joins': 2, 'conditions': 3}
        }

    def correct_sql(self, sql: str) -> Tuple[str, List[str]]:
        """增强的SQL纠正功能，添加对中文字符的支持"""
        original_sql = sql
        corrections = []
        
        # 检查插入语句中的中文值
        if 'insert' in sql.lower():
            # 检查是否缺少引号的值
            values = re.findall(r'=([^,\s]+)', sql)
            for value in values:
                # 如果值包含中文字符且没有被引号包围
                if re.search(r'[\u4e00-\u9fff]', value) and not (value.startswith("'") and value.endswith("'")):
                    old_sql = sql
                    sql = sql.replace(f'={value},', f"='{value}',")
                    sql = sql.replace(f'={value}', f"='{value}'")  # 处理最后一个值
                    if old_sql != sql:
                        corrections.append(f"为中文值 '{value}' 添加引号")
        
        # 1. 基本拼写纠正
        for category, patterns in self.common_errors.items():
            for pattern, correction in patterns:
                if re.search(pattern, sql.lower()):
                    old_sql = sql
                    sql = re.sub(pattern, correction, sql, flags=re.IGNORECASE)
                    if old_sql != sql:
                        corrections.append(f"将 '{pattern}' 更正为 '{correction}'")
                        # 添加相关命令模板建议
                        command_type = correction.split()[0] if ' ' in correction else correction
                        if command_type in self.command_templates:
                            corrections.append(f"参考语法: {self.command_templates[command_type]}")

        # 2. 智能补全
        sql_lower = sql.lower()
        first_word = sql_lower.split()[0] if sql_lower else ''
        
        if first_word in self.command_templates:
            if 'table' in sql_lower and '(' not in sql_lower:
                corrections.append("提示: 创建表需要指定列定义，例如：")
                corrections.append(self.command_templates['create']['table'])
            elif 'select' in sql_lower and 'from' not in sql_lower:
                corrections.append("提示: SELECT 语句需要 FROM 子句，例如：")
                corrections.append(self.command_templates['select']['simple'])

        # 3. 上下文相关建议
        if 'where' in sql_lower and '=' not in sql_lower and '>' not in sql_lower and '<' not in sql_lower:
            corrections.append("提示: WHERE 子句需要比较条件")
            corrections.append("例如: where column = value")

        # 4. 使用 difflib 进行模糊匹配
        if not first_word:
            return sql, ["请输入SQL命令"]
        
        if first_word not in ['create', 'select', 'insert', 'delete', 'update', 'drop', 'alter']:
            close_matches = difflib.get_close_matches(first_word, 
                ['create', 'select', 'insert', 'delete', 'update', 'drop', 'alter'],
                n=1, cutoff=0.6)
            if close_matches:
                corrections.append(f"您是不是要输入: {close_matches[0]}")
                corrections.append(f"参考语法: {self.command_templates.get(close_matches[0], '命令示例')}")

        # 检查JOIN语法
        if 'join' in sql.lower():
            # 检查并修正JOIN语法
            if re.search(r'join\s+(\w+)\s+on\s+on\s+', sql.lower()):
                sql = re.sub(r'join\s+(\w+)\s+on\s+on\s+', r'join \1 on ', sql)
                corrections.append("移除多余的 'on' 关键字")

        return sql, corrections

    def _get_sql_type(self, sql: str) -> str:
        """识别SQL语句类型"""
        sql_lower = sql.lower().strip()
        if sql_lower.startswith('select'):
            return 'select'
        elif sql_lower.startswith('insert'):
            return 'insert'
        elif sql_lower.startswith('delete'):
            return 'delete'
        elif sql_lower.startswith('update'):
            return 'update'
        elif sql_lower.startswith('create'):
            return 'create_table'
        elif sql_lower.startswith('drop'):
            return 'drop_table'
        return None

    def _check_syntax(self, sql: str, sql_type: str) -> str:
        """检查并修正SQL语法"""
        if sql_type == 'select':
            if 'join' in sql.lower() and 'on' not in sql.lower():
                raise Exception("JOIN 语句缺少 ON 条件")
            if 'where' in sql.lower() and '=' not in sql.lower() and '>' not in sql.lower() and '<' not in sql.lower():
                raise Exception("WHERE 子句缺少比较条件")

        return sql

    def _generate_suggestions(self, sql: str) -> List[str]:
        """生成SQL改进建议"""
        suggestions = []
        sql_lower = sql.lower()

        # 检查是否缺少别名
        if 'join' in sql_lower and not re.search(r'\b(as|[a-z])\b', sql_lower):
            suggestions.append("建议为表添加别名以提高可读性")

        # 检查是否使用了 SELECT *
        if 'select *' in sql_lower:
            suggestions.append("建议指定具体的列名而不是使用 *")

        # 检查条件中的引号使用
        if "where" in sql_lower:
            if not re.search(r"'[^']*'", sql):
                suggestions.append("字符串条件值应该用单引号括起来")

        return suggestions

    def analyze_query_complexity(self, sql: str) -> dict:
        """分析查询复杂度并提供优化建议"""
        analysis = {
            'complexity': 'simple',
            'reasons': [],
            'optimization_suggestions': []
        }
        
        sql_lower = sql.lower()
        
        # 计算连接数
        join_count = sql_lower.count('join')
        # 计算条件数
        condition_count = sql_lower.count('where') + sql_lower.count('and') + sql_lower.count('or')
        
        # 评估复杂度
        if join_count >= 2 or condition_count >= 3:
            analysis['complexity'] = 'complex'
            analysis['reasons'].append(f"查询包含 {join_count} 个连接和 {condition_count} 个条件")
            analysis['optimization_suggestions'].append("考虑拆分复杂查询为多个简单查询")
        elif join_count >= 1 or condition_count >= 2:
            analysis['complexity'] = 'medium'
            analysis['reasons'].append("查询包含多个连接或条件")
            analysis['optimization_suggestions'].append("考虑添加适当的索引")
            
        return analysis

    def suggest_optimizations(self, sql: str) -> List[str]:
        """提供查询优化建议"""
        suggestions = []
        sql_lower = sql.lower()
        
        # 检查子查询
        if '(select' in sql_lower:
            suggestions.append("考虑使用JOIN替代子查询以提高性能")
            
        # 检查索引使用机会
        if 'where' in sql_lower:
            suggestions.append("确保WHERE子句中的列已建立适当的索引")
            
        # 检查排序和分组
        if 'order by' in sql_lower:
            suggestions.append("在ORDER BY列上创建索引可以提高排序性能")
        if 'group by' in sql_lower:
            suggestions.append("在GROUP BY列上创建索引可以提高分组性能")
            
        return suggestions

    def suggest_indexes(self, sql: str) -> List[str]:
        """增强的索引建议功能"""
        suggestions = []
        sql_lower = sql.lower()
        
        if 'where' in sql_lower:
            # 提取WHERE条件中的列
            where_cols = re.findall(r'where\s+([a-z_][a-z0-9_]*)', sql_lower)
            for col in where_cols:
                suggestions.append(f"建议在列 {col} 上创建索引")

        if 'join' in sql_lower:
            # 提取JOIN条件中的列
            join_cols = re.findall(r'on\s+([a-z_][a-z0-9_]*)', sql_lower)
            for col in join_cols:
                suggestions.append(f"建议在连接列 {col} 上创建索引")

        # 添加复合索引建议
        if 'where' in sql_lower and 'and' in sql_lower:
            conditions = re.findall(r'where\s+(.*?)\s+and\s+(.*?)(?:\s+|$)', sql_lower)
            if conditions:
                cols = [c.split()[0] for c in conditions[0]]
                suggestions.append(f"建议创建复合索引 ({', '.join(cols)})")
                
        # 添加排序索引建议
        if 'order by' in sql_lower:
            order_cols = re.findall(r'order\s+by\s+([a-z_][a-z0-9_]*)', sql_lower)
            for col in order_cols:
                suggestions.append(f"建议在排序列 {col} 上创建索引")
                
        return suggestions 

    def check_join_syntax(self, sql: str) -> Tuple[str, List[str]]:
        """检查JOIN语法并提供建议"""
        corrections = []
        sql_lower = sql.lower()
        
        # 检查JOIN语法
        if 'join' in sql_lower:
            # 检查ON条件
            if 'on' not in sql_lower:
                corrections.append("JOIN语句需要使用ON指定连接条件")
                corrections.append("示例: table1 JOIN table2 ON table1.id = table2.id")
            
            # 检查表别名
            tables = re.findall(r'from\s+(\w+)\s+join\s+(\w+)', sql_lower)
            if tables and not re.search(r'\b(as|[a-z])\b', sql_lower):
                corrections.append("建议为表添加别名以提高可读性")
                corrections.append(f"示例: FROM {tables[0][0]} AS t1 JOIN {tables[0][1]} AS t2")
                
            # 检查连接顺序
            if tables:
                corrections.append("提示:建议将小表放在左边以优化连接性能")
                
        return sql, corrections

    def suggest_join_optimizations(self, sql: str) -> List[str]:
        """为JOIN查询提供优化建议"""
        suggestions = []
        sql_lower = sql.lower()
        
        if 'join' in sql_lower:
            # 建议创建索引
            join_cols = re.findall(r'on\s+(\w+\.\w+)\s*=\s*(\w+\.\w+)', sql_lower)
            for cols in join_cols:
                suggestions.append(f"建议在连接列 {cols[0]} 和 {cols[1]} 上创建索引")
                
            # 建议连接策略
            if 'left' in sql_lower:
                suggestions.append("使用LEFT JOIN时,建议确保右表已经建立了合适的索引")
            elif 'right' in sql_lower:
                suggestions.append("RIGHT JOIN可以改写为LEFT JOIN,通常LEFT JOIN性能更好")
                
            # 检查是否有多表连接
            join_count = sql_lower.count('join')
            if join_count > 2:
                suggestions.append("多表连接请注意连接顺序,建议先连接结果集较小的表")
                
        return suggestions 

    def suggest_ai_optimizations(self, sql: str) -> List[str]:
        """使用AI技术提供查询优化建议"""
        suggestions = []
        sql_lower = sql.lower()
        
        # 基于查询模式的建议
        if 'where' in sql_lower and 'like' in sql_lower:
            suggestions.append("发现模糊查询模式,建议添加合适的前缀索引")
            
        # 基于数据分布的建议
        if 'order by' in sql_lower:
            suggestions.append("检测到排序操作,建议分析数据分布考虑添加聚集索引")
            
        # 基于查询历史的建议
        if self._is_frequent_query(sql):
            suggestions.append("该查询模式频繁出现,建议创建物化视图")
            
        return suggestions

    def _is_frequent_query(self, sql: str) -> bool:
        """分析查询是否频繁出现"""
        # 实现查询频率分析逻辑
        return False 

    def analyze_context(self, sql: str, history: List[str]) -> List[str]:
        """基于历史命令分析上下文并提供建议"""
        suggestions = []
        
        # 分析用户操作模式
        pattern = self._detect_operation_pattern(history)
        
        # 基于模式提供建议
        if pattern == 'data_query':
            suggestions.append("建议创建针对查询模式的索引")
        elif pattern == 'data_modification':
            suggestions.append("注意事务完整性")
        
        return suggestions 

    def suggest_ml_optimizations(self, sql: str) -> List[str]:
        """使用机器学习模型提供优化建议"""
        suggestions = []
        
        # 分析查询模式
        query_pattern = self._analyze_query_pattern(sql)
        
        # 基于历史性能数据预测
        if self._predict_performance_bottleneck(query_pattern):
            suggestions.append("检测到潜在性能瓶颈，建议优化查询结构")
            
        return suggestions 

    def format_error_message(self, error: str) -> str:
        """格式化错误消息使其更易读"""
        formatted = "<b>错误提示:</b>\n"
        formatted += "• " + error + "\n"
        formatted += "\n<b>可能的解决方案:</b>\n"
        
        solutions = self._get_error_solutions(error)
        for solution in solutions:
            formatted += "• " + solution + "\n"
        
        return formatted 

    def check_syntax_realtime(self, sql: str) -> Dict:
        """实时语法检查"""
        result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'suggestions': []
        }
        
        # 检查基本语法
        if not self._check_basic_syntax(sql):
            result['valid'] = False
            result['errors'].append("SQL语法错误")
        
        # 检查最佳实践
        warnings = self._check_best_practices(sql)
        if warnings:
            result['warnings'].extend(warnings)
        
        return result 

    def analyze_join_query(self, sql: str) -> Dict:
        """分析JOIN查询并提供详细信息"""
        analysis = {
            'join_type': [],
            'tables': [],
            'conditions': [],
            'optimization_tips': []
        }
        
        sql_lower = sql.lower()
        
        # 识别JOIN类型
        if 'left join' in sql_lower:
            analysis['join_type'].append('LEFT JOIN')
        elif 'right join' in sql_lower:
            analysis['join_type'].append('RIGHT JOIN')
        elif 'inner join' in sql_lower:
            analysis['join_type'].append('INNER JOIN')
        else:
            analysis['join_type'].append('CROSS JOIN')
            
        # 提取表名
        tables = re.findall(r'from\s+(\w+)\s+(?:join\s+(\w+))', sql_lower)
        if tables:
            analysis['tables'].extend(list(tables[0]))
            
        # 提取连接条件
        conditions = re.findall(r'on\s+(\w+\.\w+)\s*=\s*(\w+\.\w+)', sql_lower)
        if conditions:
            analysis['conditions'].extend(conditions)
            
        # 生成优化建议
        analysis['optimization_tips'] = self.suggest_join_optimizations(sql)
        
        return analysis
        
    def validate_join_syntax(self, sql: str) -> Tuple[bool, List[str]]:
        """验证JOIN语法的正确性"""
        errors = []
        is_valid = True
        
        # 检查基本JOIN语法
        if 'join' in sql.lower():
            # 检查ON子句
            if 'on' not in sql.lower():
                errors.append("缺少ON子句指定连接条件")
                is_valid = False
                
            # 检查连接条件格式
            conditions = re.findall(r'on\s+(\w+\.\w+)\s*=\s*(\w+\.\w+)', sql.lower())
            if not conditions:
                errors.append("连接条件格式不正确，应为'table1.column = table2.column'")
                is_valid = False
                
            # 检查表别名
            if not re.search(r'\b(as|[a-z])\b', sql.lower()):
                errors.append("建议使用表别名提高可读性")
                
        return is_valid, errors 