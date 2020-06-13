import pickle
from django.shortcuts import render
import json

from django.views.generic.base import View
from search.models import ElectricPowerIndex
from django.http import HttpResponse
from datetime import datetime
import redis
from elasticsearch import Elasticsearch
from bidaf.predict_one import *

client = Elasticsearch(hosts=["localhost"])
# 使用redis实现top-n排行榜
redis_cli = redis.StrictRedis()


class IndexView(View):
    """首页get请求top-n排行榜"""

    @staticmethod
    def get(request):
        topn_search_clean = []
        topn_search = redis_cli.zrevrangebyscore(
            "search_keywords_set", "+inf", "-inf", start=0, num=5)
        for topn_key in topn_search:
            topn_key = str(topn_key, encoding="utf-8")
            topn_search_clean.append(topn_key)
        topn_search = topn_search_clean
        return render(request, "index.html", {"topn_search": topn_search})


class SearchSuggest(View):
    """搜索建议"""

    @staticmethod
    def get(request):
        key_words = request.GET.get('s', '')
        current_type = request.GET.get('s_type', '')
        if current_type == "article":
            return_suggest_list = []
            if key_words:
                s = ElectricPowerIndex.search()
                """fuzzy模糊搜索, fuzziness 编辑距离, prefix_length前面不变化的前缀长度"""
                s = s.suggest('my_suggest', key_words, completion={
                    "field": "suggest", "fuzzy": {
                        "fuzziness": 2
                    },
                    "size": 10
                })
                suggestions = s.execute()
                for match in suggestions.suggest.my_suggest[0].options[:10]:
                    source = match._source
                    return_suggest_list.append(source["title"])
            return HttpResponse(
                json.dumps(return_suggest_list),
                content_type="application/json")


class SearchView(View):

    def get(self, request):
        key_words = request.GET.get("q", "")

        # 通用部分
        # 实现搜索关键词keyword加1操作
        redis_cli.zincrby("search_keywords_set", 1, key_words)
        # 获取topn个搜索词
        topn_search_clean = []
        topn_search = redis_cli.zrevrangebyscore(
            "search_keywords_set", "+inf", "-inf", start=0, num=5)
        for topn_key in topn_search:
            topn_key = str(topn_key, encoding="utf-8")
            topn_search_clean.append(topn_key)
        topn_search = topn_search_clean

        # 当前要获取第几页的数据
        page = request.GET.get("p", "1")
        try:
            page = int(page)
        except BaseException:
            page = 1
        article_response = []
        question_response = []
        start_time = datetime.now()
        s_type = request.GET.get("s_type", "")
        if s_type == "article":
            article_response = client.search(
                index="electric_power",
                request_timeout=60,
                body={
                    "query": {
                        "multi_match": {
                            "query": key_words,
                            "fields": ["tags", "title", "content"]
                        }
                    },
                    "from": (page - 1) * 10,
                    "size": 10,
                    "highlight": {
                        "pre_tags": ['<span class="keyWord">'],
                        "post_tags": ['</span>'],
                        "fields": {
                            "title": {},
                            "content": {},
                        }
                    }
                }
            )

        elif s_type == "question":
            question_response = client.search(
                index="electric_power",
                request_timeout=60,
                body={
                    "query": {
                        "multi_match": {
                            "query": key_words,
                            "fields": ["tags", "title", "content"]
                        }
                    },
                    "from": (page - 1) * 10,
                    "size": 1,
                }
            )
        end_time = datetime.now()
        last_seconds = (end_time - start_time).total_seconds()

        hit_list = []
        error_nums = 0
        if s_type == "article":
            for hit in article_response["hits"]["hits"]:
                hit_dict = {}
                try:
                    if "title" in hit["highlight"]:
                        hit_dict["title"] = "".join(hit["highlight"]["title"])
                    else:
                        hit_dict["title"] = hit["_source"]["title"]
                    if "content" in hit["highlight"]:
                        hit_dict["content"] = "".join(
                            hit["highlight"]["content"])
                    else:
                        hit_dict["content"] = hit["_source"]["content"][:200]
                    hit_dict["publish_date"] = hit["_source"]["publish_time"]
                    hit_dict["crawl_date"] = hit["_source"]["crawl_time"]
                    hit_dict["url"] = hit["_source"]["url"]
                    hit_dict["score"] = hit["_score"]
                    hit_dict["source_site"] = hit["_source"]["website_name"]
                    hit_list.append(hit_dict)
                except:
                    error_nums = error_nums + 1
        elif s_type == "question":
            for hit in question_response["hits"]["hits"]:
                hit_dict = {}
                try:
                    if "title" in hit["highlight"]:
                        hit_dict["title"] = "".join(hit["highlight"]["title"])
                    else:
                        hit_dict["title"] = hit["_source"]["title"]
                    if "content" in hit["highlight"]:
                        hit_dict["content"] = "".join(
                            hit["highlight"]["content"])
                    else:
                        content = hit["_source"]["content"]
                        input_data = {
                            "documents": content,
                            "question": key_words,
                            "question_type": "ENTITY",
                            "fact_or_opinion": "FACT"
                        }
                        # 调用bi-daf进行答案生成
                        process_data = data_precess(input_data)
                        predict_output = predict_one(args, process_data)
                        hit_dict["content"] = predict_output
                    hit_dict["publish_date"] = hit["_source"]["publish_time"]
                    hit_dict["crawl_date"] = hit["_source"]["crawl_time"]
                    hit_dict["url"] = hit["_source"]["url"]
                    hit_dict["score"] = hit["_score"]
                    hit_dict["source_site"] = hit["_source"]["website_name"]
                    hit_list.append(hit_dict)
                except:
                    error_nums = error_nums + 1
        total_nums = int(article_response["hits"]["total"])

        # 计算出总页数
        if (page % 10) > 0:
            page_nums = int(total_nums / 10) + 1
        else:
            page_nums = int(total_nums / 10)
        return render(request, "result.html", {"page": page,
                                               "all_hits": hit_list,
                                               "key_words": key_words,
                                               "total_nums": total_nums,
                                               "page_nums": page_nums,
                                               "last_seconds": last_seconds,
                                               "topn_search": topn_search,
                                               })
