-- 创建人物信息表
CREATE TABLE IF NOT EXISTS person (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    worldview TEXT,
    race TEXT,
    hometown VARCHAR(255),
    gender VARCHAR(50),
    biography TEXT,
    age INTEGER,
    personality TEXT,
    cognition TEXT,
    keywords VARCHAR(255)
);

-- 向人物信息表中插入随机生成的人物数据

-- 人物1：中世纪奇幻世界的骑士
INSERT INTO person (name, worldview, race, hometown, gender, biography, age, personality, cognition, keywords)
VALUES (
    '亚瑟·兰斯特',
    '中世纪奇幻世界，魔法与剑并存，王国与骑士制度盛行',
    '人类',
    '王国北部的银松镇',
    '男性',
    '15岁：加入王国骑士学院;18岁：成为正式骑士;20岁：参与抵御兽人入侵，立下战功;25岁：被授予"银剑"称号;30岁：成为王国骑士团副团长',
    35,
    '正直勇敢，责任感强，重视荣誉，对朋友忠诚',
    '世界是一个需要守护的地方，每个人都有自己的责任，力量应该用来保护弱者',
    '骑士，荣誉，忠诚，勇敢'
);

-- 人物2：未来科幻世界的科学家
INSERT INTO person (name, worldview, race, hometown, gender, biography, age, personality, cognition, keywords)
VALUES (
    '艾莉亚·陈',
    '2150年未来世界，科技高度发达，人类已开始星际殖民',
    '人类',
    '火星殖民地新上海',
    '女性',
    '16岁：考入星际科技学院;22岁：获得量子物理学博士学位;25岁：主导开发新型空间跃迁技术;28岁：获得星际科学奖;32岁：成为地球联邦科学院最年轻的院士',
    35,
    '聪明理性，好奇心强，专注科研，对未知充满探索欲',
    '宇宙是一个无限的知识库，科技是人类进步的阶梯，探索是人类的本能',
    '科学家，探索，智慧，创新'
);

-- 人物3：奇幻世界的精灵法师
INSERT INTO person (name, worldview, race, hometown, gender, biography, age, personality, cognition, keywords)
VALUES (
    '瑟兰迪尔·星歌',
    '奇幻森林世界，精灵、矮人、人类共存，魔法元素活跃',
    '精灵，长寿，擅长魔法，对自然有亲和力，耳朵尖长',
    '永恒森林的银月谷',
    '男性',
    '100岁：完成精灵成年礼;150岁：成为高级法师;200岁：守护森林抵御黑暗生物入侵;300岁：担任精灵族魔法学院院长;400岁：与人类建立和平协议',
    450,
    '优雅冷静，重视传统，热爱自然，对朋友温和',
    '自然是一切生命的源泉，魔法是自然的馈赠，平衡是世界的本质',
    '精灵，法师，自然，智慧'
);

-- 人物4：蒸汽朋克世界的机械师
INSERT INTO person (name, worldview, race, hometown, gender, biography, age, personality, cognition, keywords)
VALUES (
    '维多利亚·铁手',
    '蒸汽朋克世界，机械与蒸汽技术发达，工业革命时代',
    '人类',
    '机械城的齿轮区',
    '女性',
    '12岁：开始学习机械制造;18岁：发明自动机械助手;22岁：修复城市核心蒸汽机;25岁：设计新型蒸汽飞艇;30岁：成为机械师公会会长',
    35,
    '活泼开朗，动手能力强，喜欢创新，坚韧不拔',
    '机械是人类智慧的结晶，蒸汽是推动世界前进的动力，创新是进步的关键',
    '机械师，创新，坚韧，技术'
);

-- 人物5：东方武侠世界的剑客
INSERT INTO person (name, worldview, race, hometown, gender, biography, age, personality, cognition, keywords)
VALUES (
    '李青云',
    '东方武侠世界，江湖门派林立，武学高手辈出',
    '人类',
    '中原华山脚下的青竹村',
    '男性',
    '8岁：拜入华山派;15岁：练成华山基础剑法;20岁：下山闯荡江湖;25岁：击败魔教高手，名震江湖;30岁：成为华山派掌门',
    35,
    '沉稳内敛，重情重义，追求武学极致，嫉恶如仇',
    '江湖是人心的江湖，武学是修身的途径，正义是为人的根本',
    '剑客，武侠，正义，修行'
);
