# -*- coding:utf-8 -*-

"""
Create on 2019/11/16 3:26 PM
@Author: dfsj
@Description: 
"""
import jieba
import os
import logging
import pickle
import argparse
from dataloader.BaiduDataLoader import BRCDataset
from model.BaiduModel import RCModel


'''Which dataset do you want to use, just choose between search and zhidao'''
dataName = 'search'


def parse_args():
    """
    Parses command line arguments.
    """
    parser = argparse.ArgumentParser('Reading Comprehension on BaiduRC dataset')
    parser.add_argument("--test_one", action='store_true', help="aaaa")

    train_settings = parser.add_argument_group('train settings')
    train_settings.add_argument('--optim', default='adam',
                                help='optimizer type')
    train_settings.add_argument('--learning_rate', type=float, default=0.001,
                                help='learning rate')
    train_settings.add_argument('--weight_decay', type=float, default=0,
                                help='weight decay')
    train_settings.add_argument('--dropout_keep_prob', type=float, default=0.5,
                                help='dropout keep rate')
    train_settings.add_argument('--batch_size', type=int, default=32,
                                help='train batch size')

    model_settings = parser.add_argument_group('model settings')
    model_settings.add_argument('--algo', choices=['BIDAF', 'MLSTM'], default='BIDAF',
                                help='choose the algorithm to use')
    model_settings.add_argument('--embed_size', type=int, default=300,
                                help='size of the embeddings')
    model_settings.add_argument('--hidden_size', type=int, default=128,
                                help='size of LSTM hidden units')
    model_settings.add_argument('--max_p_num', type=int, default=5,
                                help='max passage num in one sample')
    model_settings.add_argument('--max_p_len', type=int, default=500,
                                help='max length of passage')
    model_settings.add_argument('--max_q_len', type=int, default=60,
                                help='max length of question')
    model_settings.add_argument('--max_a_len', type=int, default=200,
                                help='max length of answer')

    path_settings = parser.add_argument_group('path settings')
    path_settings.add_argument('--vocab_dir', default='./data/vocab/' + dataName + '/',
                               help='the dir to save vocabulary')
    path_settings.add_argument('--model_dir', default='./data/models/Baidu/' + dataName + '/',
                               help='the dir to store models')
    path_settings.add_argument('--result_dir', default='./data/results/Baidu/' + dataName + '/',
                               help='the dir to output the results')
    path_settings.add_argument('--summary_dir', default='./data/summary/Baidu/' + dataName + '/',
                               help='the dir to write tensorboard summary')
    path_settings.add_argument('--log_path', default='./data/summary/Baidu/' + dataName + '/log.txt',
                               help='path of the log file. If not set, logs are printed to console')
    return parser.parse_args()


def predict_one(args, test_json_data=None):
    """
        predicts answers for test one data
        test_json_data: 示例
        {
            "documents":
            [
                {
                    "title": "揭秘宋庆龄“第二段婚姻”传言不为人知的真相 - 红色秘史 - 红潮网 ",
                    "segmented_title": "",
                    "segmented_paragraphs": [[], []],
                    "paragraphs": ["宋庆龄一生没有生养自己的孩子,鲜为人知的是,花甲之年时,她却有两个养女:隋永清和隋永洁。", ""],
                    "bs_rank_pos": 0
                    },
                    {}
            ],
            "question": "宋庆龄第二任丈夫是谁",
            "segmented_question": ["宋庆龄", "第", "二", "任", "丈夫", "是", "谁"],
            "question_type": "ENTITY",    默认为 "ENTITY"
            "fact_or_opinion": "FACT",    默认为 "FACT"
            "question_id": 221574
        }
    """
    print('Load data_set and vocab...')
    with open(os.path.join(args.vocab_dir, dataName + 'BaiduVocab.data'), 'rb') as fin:
        vocab = pickle.load(fin)

    brc_data = BRCDataset(args.max_p_num, args.max_p_len, args.max_q_len, test_one=test_json_data)
    print('Converting text into ids...')
    brc_data.convert_to_ids(vocab)

    print('Restoring the model...')
    rc_model = RCModel(vocab, args)
    rc_model.restore(model_dir=args.model_dir, model_prefix=args.algo)

    print('Predicting answers for test set...')
    test_batches = brc_data.gen_mini_batches('test', args.batch_size,
                                             pad_id=vocab.get_id(vocab.pad_token), shuffle=False)
    result = rc_model.evaluate_one(test_batches, result_dir=args.result_dir, result_prefix='test.predicted')
    return result


args = parse_args()

logger = logging.getLogger("brc")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
if args.log_path:
    file_handler = logging.FileHandler(args.log_path)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
else:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

logger.info('Running with args : {}'.format(args))


def data_precess(datas):
    """
    传入的 json 至少包含 "documents", "question", 其中 documents 至少包含 title 和 paragraphs
    paragraphs 为段落列表，所有中文逗号替换为英文
    question_type 默认值是 ENTITY
    fact_or_opinion 默认值是 FACT
    datas = {
                "documents": [
                    {"title": "XXXX", "paragraphs": ["XXX", "XX"]}],
                "question": "XXXX",
                "question_type": "XXX",
                "fact_or_opinion": "XXXX"
            }
    """
    assert "documents" in datas, "documents 必须提供"
    assert "question" in datas, "question 必须提供"
    documents = datas["documents"]
    for document in documents:
        assert "title" in document, "title 在 document 中必须提供"
        assert "paragraphs" in document, "paragraphs 在 document 中必须提供"
        assert isinstance(document["paragraphs"], list), "paragraph 需要为列表形式"
        if "segmented_title" not in document:
            document['segmented_title'] = list(jieba.cut(document['title']))
        if "segmented_paragraphs" not in document:
            document['segmented_paragraphs'] = [list(jieba.cut(item)) for item in document['paragraphs']]
            document["bs_rank_pos"] = 0
    if "segmented_question" not in datas:
        datas["segmented_question"] = list(jieba.cut(datas['question']))
    if "question_type" not in datas:
        datas["question_type"] = "ENTITY"
    if "fact_or_opinion" not in datas:
        datas["fact_or_opinion"] = "FACT"

    return datas


test_data = {"documents": [{"title": "揭秘宋庆龄“第二段婚姻”传言不为人知的真相 - 红色秘史 - 红潮网 ", "paragraphs": ["宋庆龄一生没有生养自己的孩子,鲜为人知的是,花甲之年时,她却有两个养女:隋永清和隋永洁。这一对姐妹花从出生不久,就伴在宋庆龄身边,陪她度过了人生最后的20多年。", "2014年8月,在北京西城区一家老式茶楼,环球人物杂志记者见到了隋家姐姐隋永清。她曾是一位电影演员,采访当天穿着简单的T恤,言行举止无不透着大家风范。", "宋庆龄已去世30多年,隋永清如今也年近花甲。但她保养得很好,皮肤白皙,声音清脆悦耳。采访前与隋永清短信联系时,她不失顽皮,还发来不少搞怪图片,让人很难想象这是57岁的老人。她说自己从小就“被宋庆龄宠腻坏了”。而在记者采访的几个小时里,隋永清口中的宋庆龄,也不是大家熟知的形象,更多的是一个母亲的柔软。", "一尿成了宋庆龄的女儿", "1915年秋天,宋庆龄不顾家人反对,奔赴日本与大自己27岁的孙中山结婚。追随孙中山的10年间,她曾孕育过一个生命,但在军阀陈炯明叛乱的突围中流产,这对宋庆龄是一个重大的打击。更加不幸的是,仅仅两年后,孙中山也匆匆告别人世。", "因为人生中的遗憾,宋庆龄特别喜欢孩子。周围哪家婴儿刚出生,都会找机会抱来给她看看。她还总叮嘱登门的客人“下次一定要带着孩子一起来”。", "隋永清的父亲隋学芳是东北人,在东北参军,后由公安部从部队挑选考核派到宋庆龄身边,成为她的贴身警卫秘书。“由于工作关系,父亲落户在上海。结婚后,因为工作需要,我们一家人都曾住在宋庆龄在上海住宅的配楼里。”", "1957年年底,隋学芳的大女儿隋永清出生。知道宋庆龄喜欢小孩,隋学芳就把襁褓中的女儿抱到宋庆龄面前。跟别的孩子不同,刚出生的隋永清一点也不认生,她不哭不闹,对着宋庆龄一直笑。宋庆龄正高兴时,突然觉得一阵温热,原来是孩子撒尿了。周围的人大吃一惊。大家都知道,宋庆龄是特别讲卫生的人,几双手同时伸过来,要从宋庆龄的怀里把孩子抱走。没想到,宋庆龄坚决不让别人插手,连声说道:“别动!让孩子尿完,不然会坐下病的。”大家眼睁睁地看着这个小家伙,在一辈子讲究干净的宋庆龄怀里放肆地尿了个痛快。", "谁都没料到,这一笑、一尿引起了宋庆龄的怜爱之心,她觉得同这个孩子有一种亲密的缘分,并提出希望收养这个女孩。至今,隋永清回忆起来,都说:“我觉得这种事情说不清楚,就是冥冥之中的感觉。我是被抱过去众多孩子中的一个,但我是最幸运的,被宋庆龄留下了。”", "这一年宋庆龄64岁,按年龄算,隋永清应是宋庆龄的孙辈,但宋庆龄不喜欢被人叫成阿婆、奶奶。隋永清叫她“妈妈太太”,这个称谓是刚学会说话的隋永清自己创造的。", "“她对我们几乎都是放养的”", "妹妹隋永洁出生后,也经常到宋庆龄的上海寓所玩,姐妹两人给她那清幽的寓所增添了生气。", "1959年,宋庆龄来到北京,隋永清和她一起随行,相伴左右。她说宋庆龄在北京的足迹自己都沿路跟着,“刚来的时候住在北京站对面的方巾巷,然后搬到什刹海西河沿,就是现在的郭沫若故居,1963年入住后海北河沿,如今的后海宋庆龄故居。这是宋庆龄在北京最后的住地。”到了1973年,妹妹隋永洁参军进京也住进了后海边的这所宅子。比起妹妹,隋永清在宋庆龄身边的日子更多。", "这事儿过了,保姆跟宋庆龄说:“您得管管了,她胆子太大了,哪里都敢上,闯祸了怎么办?”宋庆龄答道:“现在跟她说这些她也不懂,小孩子这个年龄就是这样。她爬那么高,还站那儿唱歌,至少这孩子勇敢、不怕高。”跟环球人物杂志记者说完这段故事,隋永清自己也乐了。", "宋庆龄常挂在嘴边的一句话是,女孩子要会打扮自己。物资紧张的困难岁月里,宋庆龄自己用着明显发旧的手绢,穿一身布衣,但对隋永清、隋永洁小时候的穿着,她下足了功夫。“那个时候的时髦料子,裙子一做就是好几条。还有冬天的小羊羔皮大衣,我们喜欢得不得了。妈妈太太还不许我们剪头发,要留得长长的。每天早上起床,她帮我梳头,要我自己攥着马尾,给我系上漂亮的蝴蝶结。”", "姐妹俩还经常跟着宋庆龄出席外事活动,隋永清清楚地记得,与柬埔寨西哈努克亲王的会面,她和妹妹都在场。“周恩来也经常来,他左右手牵着我们两个,带我们在花园里散步。”"]}, {"title": "宋庆龄第二任丈夫是谁_百度知道", "paragraphs": ["宋庆龄只有一个丈夫,就是孙中山。 　　宋庆龄在孙中山死后,作为国人敬仰的“国母”,不仅竭力维护丈夫孙中山的光辉形象,而且为中国革命事业不懈努力着。 　　一直到她逝世,她都在为人民着想。", "宋庆龄的秘书", "没有,就一个孙中山", "刚看到解禁的文件,宋在上世纪三四十年代已经改嫁了,其丈夫是宋庆龄的秘书,这是一段婚姻已经被公布,宋曾向组织申请结婚,但是组织考虑其政治影响不同意结婚,但是可以同居,并在组织内公开以夫妻身份生活,这个相关文件能查到,这段婚姻是可查的。另外还有几段恋情盛传的,其中和其警卫员的恋情大众的认可比较高。"]}, {"title": "宋庆龄第几任妻子_百度知道", "paragraphs": ["孙中山是有个儿子的 叫孙科,当过行政院长 宋庆龄至少是第二任了"]}, {"title": "宋庆龄的第二丈夫是谁_百度知道", "paragraphs": ["宋庆龄只有一个丈夫,就是孙中山。 宋庆龄在孙中山死后,作为国人敬仰的“国母”,不仅竭力维护丈夫孙中山的光辉形象,而且为中国革命事业不懈努力着。 一直到她逝世,她都在为人民着想。", "宋庆龄的生活秘书是个很能抓住女人心理的男子,年轻而健谈,对宋庆龄更是无微不至的照顾,宋庆龄也非常喜欢这个年纪可以做自己儿子的秘书。只是宋庆龄心无芥蒂,而生活秘书或许是因为宋庆龄的人格魅力,或许是因为真心爱这个老人,或许是为了所谓的遗产和地位,勇敢地向宋庆龄提出了结婚的要求,并且承诺要用自己全部的爱来照顾宋庆龄的晚年。 当时的宋庆龄也经历了很大的思想斗争,一来生活秘书跟自己年龄差距过大,会是真心对自己吗?二来自己和离婚的生活秘书结婚,会带来怎么样的轩然大波呢?最重要的是自己所处的政治地位,再婚会有阻力吗?生活秘书对宋庆龄说,结婚是两个人的事情,两个人心里有对方,其他都不是困难。当生活秘书做通两个女儿的工作,两个女儿改口叫宋庆龄“妈妈”后,宋庆龄勇敢地递上了结婚申请。 一"]}],"question": "宋庆龄第二任丈夫是谁", "question_type": "ENTITY", "fact_or_opinion": "FACT"}
datas = data_precess(test_data)
output = predict_one(args, datas)
print(output)
