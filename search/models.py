from elasticsearch_dsl import Text, Date, Keyword, Integer, Document, Completion
from elasticsearch_dsl.connections import connections
from elasticsearch_dsl import analyzer

connections.create_connection(hosts=["localhost"])

my_analyzer = analyzer('ik_smart')


class ElectricPowerIndex(Document):
    """电力"""
    suggest = Completion(analyzer=my_analyzer)

    title_id = Keyword()
    author_name = Keyword()
    website_name = Keyword()
    title = Text(analyzer="ik_smart")
    content = Text(analyzer="ik_smart")
    url = Keyword()
    publish_time = Date()
    crawl_time = Date()

    class Index:
        name = 'electric_power'


if __name__ == "__main__":
    ElectricPowerIndex.init()
