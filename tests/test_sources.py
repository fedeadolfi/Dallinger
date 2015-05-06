from wallace import sources, agents, db


class TestSources(object):

    def setup(self):
        self.db = db.init_db(drop_all=True)

    def teardown(self):
        self.db.rollback()
        self.db.close()

    def add(self, *args):
        self.db.add_all(args)
        self.db.commit()

    def test_create_random_binary_string_source(self):
        source = sources.RandomBinaryStringSource()
        self.add(source)

        assert source

    def test_transmit_random_binary_string_source(self):
        source = sources.RandomBinaryStringSource()
        agent = agents.ReplicatorAgent()
        self.db.add(source)
        self.db.add(agent)
        self.db.commit()

        source.connect_to(agent)
        self.add(source, agent)

        source.transmit(to_whom=agent)
        self.db.commit()

        agent.receive_all()
        self.db.commit()

        assert agent.infos()[0].contents in ["00", "01", "10", "11"]

    def test_broadcast_random_binary_string_source(self):
        source = sources.RandomBinaryStringSource()
        agent1 = agents.ReplicatorAgent()
        agent2 = agents.ReplicatorAgent()
        self.db.add(agent1)
        self.db.add(agent2)
        self.db.commit()
        source.connect_to(agent1)
        source.connect_to(agent2)
        self.add(source, agent1, agent2)

        source.transmit(what=source.create_information())
        self.db.commit()

        agent1.receive_all()
        agent2.receive_all()
        self.db.commit()

        assert agent1.infos()[0].contents in ["00", "01", "10", "11"]
        assert agent2.infos()[0].contents in ["00", "01", "10", "11"]
