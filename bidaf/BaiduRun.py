# -*- coding:utf8 -*-
# ==============================================================================
# Copyright 2017 Baidu.com, Inc. All Rights Reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================== 
"""
This module prepares and runs the whole system.
"""
import os
import pickle
import argparse
import logging
from dataloader.BaiduDataLoader import BRCDataset
from VocabBuild.BaiduVocab import Vocab
from model.BaiduModel import RCModel

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["CUDA_VISIBLE_DEVICES"] = "2"  ## written by Fangyueran

'''Which dataset do you want to use, just choose between search and zhidao'''
dataName = 'search'


def parse_args():
    """
    Parses command line arguments.
    """
    parser = argparse.ArgumentParser('Reading Comprehension on BaiduRC dataset')
    parser.add_argument('--prepare', action='store_true',
                        help='create the directories, prepare the vocabulary and embeddings')
    parser.add_argument('--train', action='store_true',
                        help='train the model')
    parser.add_argument('--evaluate', action='store_true',
                        help='evaluate the model on dev set')
    parser.add_argument('--predict', action='store_true',
                        help='predict the answers for test set with trained model')
    parser.add_argument('--gpu', type=str, default='2',  ## written by Fangyueran
                        help='specify gpu device')
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
    train_settings.add_argument('--epochs', type=int, default=10,
                                help='train epochs')

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
    path_settings.add_argument('--train_files', nargs='+',
                               default=['./data/demo/' + dataName + '.train.json'],
                               help='list of files that contain the preprocessed train data')
    path_settings.add_argument('--dev_files', nargs='+',
                               default=['./data/demo/' + dataName + '.dev.json'],
                               help='list of files that contain the preprocessed dev data')
    path_settings.add_argument('--test_files', nargs='+',
                               default=['./data/demo/' + dataName + '.test.json'],
                               help='list of files that contain the preprocessed test data')
    path_settings.add_argument('--save_dir', default='./data/baidu',
                               help='the dir with preprocessed baidu reading comprehension data')
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
    path_settings.add_argument('--pretrained_word_path', default=None,
                               help='path of the log file. If not set, logs are printed to console')
    path_settings.add_argument('--pretrained_char_path', default=None,
                               help='path of the log file. If not set, logs are printed to console')
    return parser.parse_args()


def prepare(args):
    """
    checks data, creates the directories, prepare the vocabulary and embeddings
    """
    logger = logging.getLogger("brc")
    logger.info('Checking the data files...')
    print('Checking the data files...')
    for data_path in args.train_files + args.dev_files + args.test_files:
        assert os.path.exists(data_path), '{} file does not exist.'.format(data_path)
    logger.info('Preparing the directories...')
    for dir_path in [args.vocab_dir, args.model_dir, args.result_dir, args.summary_dir]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

    logger.info('Building vocabulary...')
    print('Building vocabulary...')
    brc_data = BRCDataset(args.max_p_num, args.max_p_len, args.max_q_len,
                          args.train_files, args.dev_files, args.test_files)
    vocab = Vocab(lower=True)
    for word in brc_data.word_iter('train'):
        vocab.add(word)

    unfiltered_vocab_size = vocab.size()
    vocab.filter_tokens_by_cnt(min_cnt=2)
    filtered_num = unfiltered_vocab_size - vocab.size()
    logger.info('After filter {} tokens, the final vocab size is {}'.format(filtered_num,
                                                                            vocab.size()))

    logger.info('Assigning embeddings...')
    vocab.randomly_init_embeddings(args.embed_size)

    logger.info('Saving vocab...')
    print('Saving vocab...')
    with open(os.path.join(args.vocab_dir, dataName + 'BaiduVocab.data'), 'wb') as fout:
        pickle.dump(vocab, fout)

    logger.info('Done with preparing!')


def train(args):
    """
    trains the reading comprehension model
    """
    logger = logging.getLogger("brc")
    logger.info('Load data_set and vocab...')
    print('Load data_set and vocab...')
    with open(os.path.join(args.vocab_dir, dataName + 'BaiduVocab.data'), 'rb') as fin:
        vocab = pickle.load(fin)
    brc_data = BRCDataset(args.max_p_num, args.max_p_len, args.max_q_len,
                          args.train_files, args.dev_files)
    logger.info('Converting text into ids...')
    print('Converting text into ids...')
    brc_data.convert_to_ids(vocab)
    logger.info('Initialize the model...')
    rc_model = RCModel(vocab, args)
    logger.info('Training the model...')
    print('Training the model...')
    rc_model.train(brc_data, args.epochs, args.batch_size, save_dir=args.model_dir,
                   save_prefix=args.algo,
                   dropout_keep_prob=args.dropout_keep_prob)
    logger.info('Done with model training!')


def evaluate(args):
    """
    evaluate the trained model on dev files
    """
    logger = logging.getLogger("brc")
    logger.info('Load data_set and vocab...')
    print('Load data_set and vocab...')
    with open(os.path.join(args.vocab_dir, dataName + 'BaiduVocab.data'), 'rb') as fin:
        vocab = pickle.load(fin)
    assert len(args.dev_files) > 0, 'No dev files are provided.'
    brc_data = BRCDataset(args.max_p_num, args.max_p_len, args.max_q_len, dev_files=args.dev_files)
    logger.info('Converting text into ids...')
    print('Converting text into ids...')
    brc_data.convert_to_ids(vocab)
    logger.info('Restoring the model...')
    print('Restoring the model...')
    rc_model = RCModel(vocab, args)
    rc_model.restore(model_dir=args.model_dir, model_prefix=args.algo)
    logger.info('Evaluating the model on dev set...')
    print('Evaluating the model on dev set...')
    dev_batches = brc_data.gen_mini_batches('dev', args.batch_size,
                                            pad_id=vocab.get_id(vocab.pad_token), shuffle=False)
    dev_loss, dev_bleu_rouge = rc_model.evaluate(
        dev_batches, result_dir=args.result_dir, result_prefix='dev.predicted')
    logger.info('Loss on dev set: {}'.format(dev_loss))
    logger.info('Result on dev set: {}'.format(dev_bleu_rouge))
    logger.info('Predicted answers are saved to {}'.format(os.path.join(args.result_dir)))


def predict(args):
    """
    predicts answers for test files
    """
    logger = logging.getLogger("brc")
    logger.info('Load data_set and vocab...')
    print('Load data_set and vocab...')
    with open(os.path.join(args.vocab_dir, dataName + 'BaiduVocab.data'), 'rb') as fin:
        vocab = pickle.load(fin)
    assert len(args.test_files) > 0, 'No test files are provided.'
    brc_data = BRCDataset(args.max_p_num, args.max_p_len, args.max_q_len,
                          test_files=args.test_files)
    logger.info('Converting text into ids...')
    print('Converting text into ids...')
    brc_data.convert_to_ids(vocab)
    logger.info('Restoring the model...')
    print('Restoring the model...')
    rc_model = RCModel(vocab, args)
    rc_model.restore(model_dir=args.model_dir, model_prefix=args.algo)
    logger.info('Predicting answers for test set...')
    print('Predicting answers for test set...')
    test_batches = brc_data.gen_mini_batches('test', args.batch_size,
                                             pad_id=vocab.get_id(vocab.pad_token), shuffle=False)
    rc_model.evaluate(test_batches,
                      result_dir=args.result_dir, result_prefix='test.predicted')


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
    logger = logging.getLogger("brc")
    logger.info('Load data_set and vocab...')
    print('Load data_set and vocab...')
    with open(os.path.join(args.vocab_dir, dataName + 'BaiduVocab.data'), 'rb') as fin:
        vocab = pickle.load(fin)

    brc_data = BRCDataset(args.max_p_num, args.max_p_len, args.max_q_len, test_one=test_json_data)
    logger.info('Converting text into ids...')
    print('Converting text into ids...')
    brc_data.convert_to_ids(vocab)
    logger.info('Restoring the model...')
    print('Restoring the model...')
    rc_model = RCModel(vocab, args)
    rc_model.restore(model_dir=args.model_dir, model_prefix=args.algo)
    logger.info('Predicting answers for test set...')
    print('Predicting answers for test set...')
    test_batches = brc_data.gen_mini_batches('test', args.batch_size,
                                             pad_id=vocab.get_id(vocab.pad_token), shuffle=False)
    rc_model.evaluate(test_batches,
                      result_dir=args.result_dir, result_prefix='test.predicted')


def run():
    """
    Prepares and runs the whole system.
    """
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

    os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu

    if args.prepare:
        prepare(args)
    if args.train:
        train(args)
    if args.evaluate:
        evaluate(args)
    if args.predict:
        predict(args)
    if args.test_one:
        datas = {"documents": [{"title": "揭秘宋庆龄“第二段婚姻”传言不为人知的真相 - 红色秘史 - 红潮网 ", "segmented_title": ["揭秘", "宋庆龄", "“", "第", "二", "段", "婚姻", "”", "传言", "不为人知", "的", "真相", "-", "红色", "秘史", "-", "红潮", "网"], "segmented_paragraphs": [["宋庆龄", "一生", "没有", "生", "养", "自己", "的", "孩子", ",", "鲜为人知", "的", "是", ",", "花甲之年", "时", ",", "她", "却", "有", "两", "个", "养女", ":", "隋永清", "和", "隋", "永", "洁", "。", "这", "一", "对", "姐妹花", "从", "出生", "不", "久", ",", "就", "伴", "在", "宋庆龄", "身边", ",", "陪", "她", "度过", "了", "人生", "最后", "的", "20", "多", "年", "。"], ["2014", "年", "8", "月", ",", "在", "北京", "西城区", "一", "家", "老式", "茶楼", ",", "环球人物", "杂志", "记者", "见到", "了", "隋", "家", "姐姐", "隋永清", "。", "她", "曾", "是", "一", "位", "电影", "演员", ",", "采访", "当天", "穿着", "简单", "的", "T恤", ",", "言行举止", "无", "不", "透", "着", "大家风范", "。"], ["宋庆龄", "已", "去世", "30", "多", "年", ",", "隋永清", "如今", "也", "年近花甲", "。", "但", "她", "保养", "得", "很好", ",", "皮肤白皙", ",", "声音", "清脆悦耳", "。", "采访", "前", "与", "隋永清", "短信", "联系", "时", ",", "她", "不", "失", "顽皮", ",", "还", "发", "来", "不", "少", "搞怪", "图片", ",", "让", "人", "很难想象", "这", "是", "57", "岁", "的", "老人", "。", "她说", "自己", "从小", "就", "“", "被", "宋庆龄", "宠", "腻", "坏", "了", "”", "。", "而", "在", "记者", "采访", "的", "几个", "小时", "里", ",", "隋永清", "口", "中", "的", "宋庆龄", ",", "也", "不是", "大家", "熟知", "的", "形象", ",", "更多", "的", "是", "一", "个", "母亲", "的", "柔软", "。"], ["一", "尿", "成", "了", "宋庆龄", "的", "女儿"], ["1915", "年", "秋天", ",", "宋庆龄", "不", "顾", "家人", "反对", ",", "奔赴", "日本", "与", "大", "自己", "27", "岁", "的", "孙中山", "结婚", "。", "追随", "孙中山", "的", "10", "年", "间", ",", "她", "曾", "孕育", "过", "一", "个", "生命", ",", "但", "在", "军阀", "陈炯明", "叛乱", "的", "突围", "中", "流产", ",", "这", "对", "宋庆龄", "是", "一", "个", "重大", "的", "打击", "。", "更加", "不幸", "的", "是", ",", "仅仅", "两年后", ",", "孙中山", "也", "匆匆", "告", "别人", "世", "。"], ["因为", "人生", "中", "的", "遗憾", ",", "宋庆龄", "特别", "喜欢", "孩子", "。", "周围", "哪家", "婴儿", "刚", "出生", ",", "都会", "找", "机会", "抱", "来", "给", "她", "看看", "。", "她", "还", "总", "叮嘱", "登门", "的", "客人", "“", "下次", "一定要", "带", "着", "孩子", "一起来", "”", "。"], ["隋永清", "的", "父亲", "隋学芳", "是", "东北人", ",", "在", "东北", "参军", ",", "后", "由", "公安部", "从", "部队", "挑选", "考核", "派", "到", "宋庆龄", "身边", ",", "成为", "她", "的", "贴身", "警卫", "秘书", "。", "“", "由于", "工作", "关系", ",", "父亲", "落户", "在", "上海", "。", "结婚后", ",", "因为", "工作", "需要", ",", "我们一家人", "都", "曾", "住在", "宋庆龄", "在", "上海", "住宅", "的", "配", "楼", "里", "。", "”"], ["1957", "年", "年底", ",", "隋学芳", "的", "大女儿", "隋永清", "出生", "。", "知道", "宋庆龄", "喜欢", "小孩", ",", "隋学芳", "就", "把", "襁褓", "中", "的", "女儿", "抱", "到", "宋庆龄", "面前", "。", "跟", "别", "的", "孩子", "不同", ",", "刚", "出生", "的", "隋永清", "一点", "也", "不", "认生", ",", "她", "不哭", "不", "闹", ",", "对着", "宋庆龄", "一直", "笑", "。", "宋庆龄", "正", "高兴", "时", ",", "突然", "觉得", "一", "阵", "温", "热", ",", "原来", "是", "孩子", "撒尿", "了", "。", "周围", "的", "人", "大吃一惊", "。", "大家都知道", ",", "宋庆龄", "是", "特别", "讲卫生", "的", "人", ",", "几", "双手", "同时", "伸", "过来", ",", "要", "从", "宋庆龄", "的", "怀里", "把", "孩子", "抱走", "。", "没想到", ",", "宋庆龄", "坚决", "不", "让", "别人", "插", "手", ",", "连", "声", "说", "道", ":", "“", "别动", "!", "让", "孩子", "尿", "完", ",", "不", "然", "会", "坐下", "病", "的", "。", "”", "大家", "眼睁睁", "地", "看着", "这个", "小家伙", ",", "在", "一辈子", "讲究", "干净", "的", "宋庆龄", "怀里", "放肆", "地", "尿", "了", "个", "痛快", "。"], ["谁", "都", "没料到", ",", "这", "一笑", "、", "一", "尿", "引起", "了", "宋庆龄", "的", "怜爱", "之", "心", ",", "她", "觉得", "同", "这个孩子", "有", "一", "种", "亲密", "的", "缘分", ",", "并", "提出", "希望", "收养", "这个", "女孩", "。", "至今", ",", "隋永清", "回忆", "起来", ",", "都", "说", ":", "“", "我", "觉得", "这种事情", "说", "不清楚", ",", "就是", "冥冥之中", "的", "感觉", "。", "我", "是", "被", "抱", "过去", "众多", "孩子", "中", "的", "一", "个", ",", "但", "我", "是", "最", "幸运", "的", ",", "被", "宋庆龄", "留下", "了", "。", "”"], ["这一年", "宋庆龄", "64", "岁", ",", "按", "年龄", "算", ",", "隋永清", "应是", "宋庆龄", "的", "孙辈", ",", "但", "宋庆龄", "不喜欢", "被", "人", "叫", "成", "阿婆", "、", "奶奶", "。", "隋永清", "叫", "她", "“", "妈妈", "太太", "”", ",", "这个", "称谓", "是", "刚", "学会", "说话", "的", "隋永清", "自己", "创造", "的", "。"], ["“", "她", "对", "我们", "几乎", "都是", "放养", "的", "”"], ["妹妹", "隋", "永", "洁", "出生", "后", ",", "也", "经常", "到", "宋庆龄", "的", "上海", "寓", "所", "玩", ",", "姐妹", "两人", "给", "她", "那", "清幽", "的", "寓", "所", "增添", "了", "生气", "。"], ["1959", "年", ",", "宋庆龄", "来到", "北京", ",", "隋永清", "和", "她", "一起", "随行", ",", "相伴", "左右", "。", "她说", "宋庆龄", "在", "北京", "的", "足迹", "自己", "都", "沿", "路", "跟着", ",", "“", "刚来", "的", "时候", "住在", "北京站", "对面", "的", "方巾巷", ",", "然后", "搬到", "什刹海", "西河沿", ",", "就是", "现在", "的", "郭沫若故居", ",", "1963", "年", "入住", "后海", "北河沿", ",", "如今", "的", "后海", "宋庆龄故居", "。", "这", "是", "宋庆龄", "在", "北京", "最后", "的", "住", "地", "。", "”", "到", "了", "1973", "年", ",", "妹妹", "隋", "永", "洁", "参军", "进京", "也", "住", "进", "了", "后", "海边", "的", "这", "所", "宅子", "。", "比", "起", "妹妹", ",", "隋永清", "在", "宋庆龄", "身边的日子", "更多", "。"], ["这事儿", "过", "了", ",", "保姆", "跟", "宋庆龄", "说", ":", "“", "您", "得", "管", "管", "了", ",", "她", "胆子", "太", "大", "了", ",", "哪里", "都", "敢", "上", ",", "闯祸", "了", "怎么办", "?", "”", "宋庆龄", "答", "道", ":", "“", "现在", "跟", "她说", "这些", "她", "也", "不懂", ",", "小孩子", "这个", "年龄", "就是这样", "。", "她", "爬", "那么", "高", ",", "还", "站", "那儿", "唱歌", ",", "至少", "这", "孩子", "勇敢", "、", "不怕", "高", "。", "”", "跟", "环球人物", "杂志", "记者", "说", "完", "这", "段", "故事", ",", "隋永清", "自己", "也", "乐", "了", "。"], ["宋庆龄", "常", "挂", "在", "嘴边", "的", "一句话", "是", ",", "女孩子", "要", "会", "打扮", "自己", "。", "物资", "紧张", "的", "困难", "岁月", "里", ",", "宋庆龄", "自己", "用", "着", "明显", "发", "旧", "的", "手绢", ",", "穿", "一", "身", "布衣", ",", "但", "对", "隋永清", "、", "隋", "永", "洁", "小时候", "的", "穿着", ",", "她", "下", "足", "了", "功夫", "。", "“", "那个时候", "的", "时髦", "料子", ",", "裙子", "一", "做", "就是", "好", "几", "条", "。", "还有", "冬天", "的", "小羊羔", "皮大衣", ",", "我们", "喜欢", "得", "不得了", "。", "妈妈", "太太", "还", "不许", "我们", "剪", "头发", ",", "要", "留", "得", "长", "长", "的", "。", "每天", "早上", "起床", ",", "她", "帮", "我", "梳头", ",", "要", "我", "自己", "攥", "着", "马尾", ",", "给", "我", "系", "上", "漂亮", "的", "蝴蝶结", "。", "”"], ["姐妹俩", "还", "经常", "跟着", "宋庆龄", "出席", "外事", "活动", ",", "隋永清", "清楚", "地", "记得", ",", "与", "柬埔寨", "西哈努克亲王", "的", "会", "面", ",", "她", "和", "妹妹", "都", "在", "场", "。", "“", "周恩来", "也", "经常", "来", ",", "他", "左右手", "牵", "着", "我们", "两", "个", ",", "带", "我们", "在", "花园里", "散步", "。", "”"]], "paragraphs": ["宋庆龄一生没有生养自己的孩子,鲜为人知的是,花甲之年时,她却有两个养女:隋永清和隋永洁。这一对姐妹花从出生不久,就伴在宋庆龄身边,陪她度过了人生最后的20多年。", "2014年8月,在北京西城区一家老式茶楼,环球人物杂志记者见到了隋家姐姐隋永清。她曾是一位电影演员,采访当天穿着简单的T恤,言行举止无不透着大家风范。", "宋庆龄已去世30多年,隋永清如今也年近花甲。但她保养得很好,皮肤白皙,声音清脆悦耳。采访前与隋永清短信联系时,她不失顽皮,还发来不少搞怪图片,让人很难想象这是57岁的老人。她说自己从小就“被宋庆龄宠腻坏了”。而在记者采访的几个小时里,隋永清口中的宋庆龄,也不是大家熟知的形象,更多的是一个母亲的柔软。", "一尿成了宋庆龄的女儿", "1915年秋天,宋庆龄不顾家人反对,奔赴日本与大自己27岁的孙中山结婚。追随孙中山的10年间,她曾孕育过一个生命,但在军阀陈炯明叛乱的突围中流产,这对宋庆龄是一个重大的打击。更加不幸的是,仅仅两年后,孙中山也匆匆告别人世。", "因为人生中的遗憾,宋庆龄特别喜欢孩子。周围哪家婴儿刚出生,都会找机会抱来给她看看。她还总叮嘱登门的客人“下次一定要带着孩子一起来”。", "隋永清的父亲隋学芳是东北人,在东北参军,后由公安部从部队挑选考核派到宋庆龄身边,成为她的贴身警卫秘书。“由于工作关系,父亲落户在上海。结婚后,因为工作需要,我们一家人都曾住在宋庆龄在上海住宅的配楼里。”", "1957年年底,隋学芳的大女儿隋永清出生。知道宋庆龄喜欢小孩,隋学芳就把襁褓中的女儿抱到宋庆龄面前。跟别的孩子不同,刚出生的隋永清一点也不认生,她不哭不闹,对着宋庆龄一直笑。宋庆龄正高兴时,突然觉得一阵温热,原来是孩子撒尿了。周围的人大吃一惊。大家都知道,宋庆龄是特别讲卫生的人,几双手同时伸过来,要从宋庆龄的怀里把孩子抱走。没想到,宋庆龄坚决不让别人插手,连声说道:“别动!让孩子尿完,不然会坐下病的。”大家眼睁睁地看着这个小家伙,在一辈子讲究干净的宋庆龄怀里放肆地尿了个痛快。", "谁都没料到,这一笑、一尿引起了宋庆龄的怜爱之心,她觉得同这个孩子有一种亲密的缘分,并提出希望收养这个女孩。至今,隋永清回忆起来,都说:“我觉得这种事情说不清楚,就是冥冥之中的感觉。我是被抱过去众多孩子中的一个,但我是最幸运的,被宋庆龄留下了。”", "这一年宋庆龄64岁,按年龄算,隋永清应是宋庆龄的孙辈,但宋庆龄不喜欢被人叫成阿婆、奶奶。隋永清叫她“妈妈太太”,这个称谓是刚学会说话的隋永清自己创造的。", "“她对我们几乎都是放养的”", "妹妹隋永洁出生后,也经常到宋庆龄的上海寓所玩,姐妹两人给她那清幽的寓所增添了生气。", "1959年,宋庆龄来到北京,隋永清和她一起随行,相伴左右。她说宋庆龄在北京的足迹自己都沿路跟着,“刚来的时候住在北京站对面的方巾巷,然后搬到什刹海西河沿,就是现在的郭沫若故居,1963年入住后海北河沿,如今的后海宋庆龄故居。这是宋庆龄在北京最后的住地。”到了1973年,妹妹隋永洁参军进京也住进了后海边的这所宅子。比起妹妹,隋永清在宋庆龄身边的日子更多。", "这事儿过了,保姆跟宋庆龄说:“您得管管了,她胆子太大了,哪里都敢上,闯祸了怎么办?”宋庆龄答道:“现在跟她说这些她也不懂,小孩子这个年龄就是这样。她爬那么高,还站那儿唱歌,至少这孩子勇敢、不怕高。”跟环球人物杂志记者说完这段故事,隋永清自己也乐了。", "宋庆龄常挂在嘴边的一句话是,女孩子要会打扮自己。物资紧张的困难岁月里,宋庆龄自己用着明显发旧的手绢,穿一身布衣,但对隋永清、隋永洁小时候的穿着,她下足了功夫。“那个时候的时髦料子,裙子一做就是好几条。还有冬天的小羊羔皮大衣,我们喜欢得不得了。妈妈太太还不许我们剪头发,要留得长长的。每天早上起床,她帮我梳头,要我自己攥着马尾,给我系上漂亮的蝴蝶结。”", "姐妹俩还经常跟着宋庆龄出席外事活动,隋永清清楚地记得,与柬埔寨西哈努克亲王的会面,她和妹妹都在场。“周恩来也经常来,他左右手牵着我们两个,带我们在花园里散步。”"], "bs_rank_pos": 0}, {"title": "宋庆龄第二任丈夫是谁_百度知道", "segmented_title": ["宋庆龄", "第", "二", "任", "丈夫", "是", "谁", "_", "百度", "知道"], "segmented_paragraphs": [["一", "、", "名义", "上", ":", "宋庆龄", "只有", "一", "个", "丈夫", ",", "就是", "孙中山", "。", "宋庆龄", "在", "孙中山", "死后", ",", "作为", "国", "人", "敬仰", "的", "“", "国母", "”", ",", "不仅", "竭力", "维护", "丈夫", "孙中山", "的", "光辉", "形象", ",", "而且", "为", "中国", "革命", "事业", "不懈努力", "着", "。", "一直", "到", "她", "逝世", ",", "她", "都", "在", "为", "人民", "着", "想", "。", "二", "、", "实际上", "虽然", "她", "没有", "结婚", ",", "我", "想", "应该", "有情人", ",", "比如说", "侍从", "、", "工作", "人员", "、", "年轻", "秘书", ",", "一个女人", ",", "那么", "多", "年", ",", "你", "懂", "的", "。"]], "paragraphs": ["一、名义上:宋庆龄只有一个丈夫,就是孙中山。宋庆龄在孙中山死后,作为国人敬仰的“国母”,不仅竭力维护丈夫孙中山的光辉形象,而且为中国革命事业不懈努力着。 一直到她逝世,她都在为人民着想。 二、实际上虽然她没有结婚,我想应该有情人,比如说侍从、工作人员、年轻秘书,一个女人,那么多年,你懂的。"], "bs_rank_pos": 1}, {"title": "宋庆龄第二任丈夫是谁?_百度知道", "segmented_title": ["宋庆龄", "第", "二", "任", "丈夫", "是", "谁", "?", "_", "百度", "知道"], "segmented_paragraphs": [["宋庆龄", "只有", "一", "个", "丈夫", ",", "就是", "孙中山", "。", "　　", "宋庆龄", "在", "孙中山", "死后", ",", "作为", "国", "人", "敬仰", "的", "“", "国母", "”", ",", "不仅", "竭力", "维护", "丈夫", "孙中山", "的", "光辉", "形象", ",", "而且", "为", "中国", "革命", "事业", "不懈努力", "着", "。", "　　", "一直", "到", "她", "逝世", ",", "她", "都", "在", "为", "人民", "着", "想", "。"], ["宋庆龄", "的", "秘书"], ["没有", ",", "就", "一", "个", "孙中山"], ["刚看到", "解禁", "的", "文件", ",", "宋", "在", "上", "世纪", "三", "四", "十", "年代", "已经", "改嫁", "了", ",", "其", "丈夫", "是", "宋庆龄", "的", "秘书", ",", "这", "是", "一", "段", "婚姻", "已经", "被", "公布", ",", "宋", "曾", "向", "组织", "申请", "结婚", ",", "但是", "组织", "考虑", "其", "政治", "影响", "不同意", "结婚", ",", "但是", "可以", "同居", ",", "并", "在", "组织", "内", "公开", "以", "夫妻", "身份", "生活", ",", "这个", "相关文件", "能", "查", "到", ",", "这", "段", "婚姻", "是", "可", "查", "的", "。", "另外", "还有", "几", "段", "恋情", "盛传", "的", ",", "其中", "和", "其", "警卫员", "的", "恋情", "大众", "的", "认可", "比较", "高", "。"]], "paragraphs": ["宋庆龄只有一个丈夫,就是孙中山。 　　宋庆龄在孙中山死后,作为国人敬仰的“国母”,不仅竭力维护丈夫孙中山的光辉形象,而且为中国革命事业不懈努力着。 　　一直到她逝世,她都在为人民着想。", "宋庆龄的秘书", "没有,就一个孙中山", "刚看到解禁的文件,宋在上世纪三四十年代已经改嫁了,其丈夫是宋庆龄的秘书,这是一段婚姻已经被公布,宋曾向组织申请结婚,但是组织考虑其政治影响不同意结婚,但是可以同居,并在组织内公开以夫妻身份生活,这个相关文件能查到,这段婚姻是可查的。另外还有几段恋情盛传的,其中和其警卫员的恋情大众的认可比较高。"], "bs_rank_pos": 2}, {"title": "宋庆龄第几任妻子_百度知道", "segmented_title": ["宋庆龄", "第", "几", "任", "妻子", "_", "百度", "知道"], "segmented_paragraphs": [["孙中山", "是", "有", "个", "儿子", "的", "叫", "孙科", ",", "当", "过", "行政", "院长", "宋庆龄", "至少", "是", "第", "二", "任", "了"]], "paragraphs": ["孙中山是有个儿子的 叫孙科,当过行政院长 宋庆龄至少是第二任了"], "bs_rank_pos": 3}, {"title": "宋庆龄的第二丈夫是谁_百度知道", "segmented_title": ["宋庆龄", "的", "第", "二", "丈夫", "是", "谁", "_", "百度", "知道"], "segmented_paragraphs": [["宋庆龄", "只有", "一", "个", "丈夫", ",", "就是", "孙中山", "。", "宋庆龄", "在", "孙中山", "死后", ",", "作为", "国", "人", "敬仰", "的", "“", "国母", "”", ",", "不仅", "竭力", "维护", "丈夫", "孙中山", "的", "光辉", "形象", ",", "而且", "为", "中国", "革命", "事业", "不懈努力", "着", "。", "一直", "到", "她", "逝世", ",", "她", "都", "在", "为", "人民", "着", "想", "。"], ["宋庆龄", "的", "生活", "秘书", "是", "个", "很", "能", "抓住", "女人", "心理", "的", "男子", ",", "年轻", "而", "健谈", ",", "对", "宋庆龄", "更", "是", "无微不至", "的", "照顾", ",", "宋庆龄", "也", "非常喜欢", "这个", "年纪", "可以", "做自己", "儿子", "的", "秘书", "。", "只是", "宋庆龄", "心", "无", "芥蒂", ",", "而", "生活", "秘书", "或许", "是因为", "宋庆龄", "的", "人格魅力", ",", "或许", "是因为", "真心", "爱", "这个", "老人", ",", "或许", "是", "为了", "所谓", "的", "遗产", "和", "地位", ",", "勇敢", "地", "向", "宋庆龄", "提出", "了", "结婚", "的", "要求", ",", "并且", "承诺", "要", "用", "自己", "全部的爱", "来", "照顾", "宋庆龄", "的", "晚年", "。", "当时", "的", "宋庆龄", "也", "经历", "了", "很大", "的", "思想", "斗争", ",", "一", "来", "生活", "秘书", "跟", "自己", "年龄", "差距", "过", "大", ",", "会", "是", "真心", "对", "自己", "吗", "?", "二", "来", "自己", "和", "离婚", "的", "生活", "秘书", "结婚", ",", "会", "带来", "怎么样", "的", "轩然大波", "呢", "?", "最", "重要", "的", "是", "自己", "所", "处", "的", "政治", "地位", ",", "再婚", "会", "有", "阻力", "吗", "?", "生活", "秘书", "对", "宋庆龄", "说", ",", "结婚", "是", "两个人", "的", "事情", ",", "两个人", "心里", "有", "对方", ",", "其他", "都", "不是", "困难", "。", "当", "生活", "秘书", "做", "通", "两", "个", "女儿", "的", "工作", ",", "两", "个", "女儿", "改口", "叫", "宋庆龄", "“", "妈妈", "”", "后", ",", "宋庆龄", "勇敢", "地", "递", "上", "了", "结婚", "申请", "。", "一"]], "paragraphs": ["宋庆龄只有一个丈夫,就是孙中山。 宋庆龄在孙中山死后,作为国人敬仰的“国母”,不仅竭力维护丈夫孙中山的光辉形象,而且为中国革命事业不懈努力着。 一直到她逝世,她都在为人民着想。", "宋庆龄的生活秘书是个很能抓住女人心理的男子,年轻而健谈,对宋庆龄更是无微不至的照顾,宋庆龄也非常喜欢这个年纪可以做自己儿子的秘书。只是宋庆龄心无芥蒂,而生活秘书或许是因为宋庆龄的人格魅力,或许是因为真心爱这个老人,或许是为了所谓的遗产和地位,勇敢地向宋庆龄提出了结婚的要求,并且承诺要用自己全部的爱来照顾宋庆龄的晚年。 当时的宋庆龄也经历了很大的思想斗争,一来生活秘书跟自己年龄差距过大,会是真心对自己吗?二来自己和离婚的生活秘书结婚,会带来怎么样的轩然大波呢?最重要的是自己所处的政治地位,再婚会有阻力吗?生活秘书对宋庆龄说,结婚是两个人的事情,两个人心里有对方,其他都不是困难。当生活秘书做通两个女儿的工作,两个女儿改口叫宋庆龄“妈妈”后,宋庆龄勇敢地递上了结婚申请。 一"], "bs_rank_pos": 4}], "question": "宋庆龄第二任丈夫是谁", "segmented_question": ["宋庆龄", "第", "二", "任", "丈夫", "是", "谁"], "question_type": "ENTITY", "fact_or_opinion": "FACT"}
        predict_one(args, datas)


if __name__ == '__main__':
    run()
