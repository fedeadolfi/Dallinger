from wallace import agents, information, db, models
from wallace.information import Meme, Gene
from nose.tools import raises


class TestAgents(object):

    def setup(self):
        self.db = db.init_db(drop_all=True)

    def teardown(self):
        self.db.rollback()
        self.db.close()

    def add(self, *args):
        self.db.add_all(args)
        self.db.commit()

    def test_create_agent_generic(self):
        agent = agents.Agent()
        self.add(agent)

        assert agent

    def test_create_agent_generic_transmit_to_all(self):
        agent1 = agents.Agent()
        agent2 = agents.Agent()
        agent3 = agents.Agent()

        self.add(agent1)
        self.add(agent2)
        self.add(agent3)
        self.db.commit()

        agent1.connect_to(agent2)
        agent1.connect_to(agent3)
        self.add(agent1, agent2, agent3)
        agent1.transmit(to_whom=models.Node)

    def test_kill_agent(self):
        agent = agents.Agent()
        self.add(agent)

        assert agent.status == "alive"

        agent.kill()
        assert agent.status == "dead"

    def test_fail_agent(self):
        agent = agents.Agent()
        self.add(agent)

        assert agent.status == "alive"
        assert agent.time_of_death is None

        agent.fail()
        assert agent.status == "failed"
        assert agent.time_of_death is not None

    def test_create_replicator_agent(self):
        agent = agents.ReplicatorAgent()
        self.add(agent)

        assert len(agent.infos()) is 0

        info = information.Info(origin=agent, contents="foo")
        self.add(info)
        self.db.commit()

        assert agent.infos()[0] == info

    def test_agent_transmit(self):
        agent1 = agents.ReplicatorAgent()
        agent2 = agents.ReplicatorAgent()
        self.add(agent1)
        self.add(agent2)
        self.db.commit()
        agent1.connect_to(agent2)
        info = models.Info(origin=agent1, contents="foo")
        self.add(agent1, agent2, info)
        self.db.commit()

        agent1.transmit(to_whom=agent2)
        self.db.commit()

        agent2.receive_all()
        self.db.commit()

        assert agent1.infos()[0].contents == agent2.infos()[0].contents
        assert agent1.infos()[0].uuid != agent2.infos()[0].uuid

        transmission = info.transmissions[0]
        assert transmission.info_uuid == info.uuid
        assert transmission.origin_uuid == agent1.uuid
        assert transmission.destination_uuid == agent2.uuid

    @raises(ValueError)
    def test_agent_transmit_no_connection(self):
        agent1 = agents.ReplicatorAgent()
        agent2 = agents.ReplicatorAgent()
        info = models.Info(origin=agent1, contents="foo")
        self.add(agent1, agent2, info)
        agent1.transmit(what=info, to_whom=agent2)
        self.db.commit()

    @raises(ValueError)
    def test_agent_transmit_invalid_info(self):
        agent1 = agents.ReplicatorAgent()
        agent2 = agents.ReplicatorAgent()
        self.add(agent1)
        self.add(agent2)
        self.db.commit()

        agent1.connect_to(agent2)
        info = models.Info(origin=agent2, contents="foo")
        self.add(agent1, agent2, info)

        agent1.transmit(what=info, to_whom=agent2)
        self.db.commit()

    def test_agent_transmit_everything_to_everyone(self):
        agent1 = agents.ReplicatorAgent()
        agent2 = agents.ReplicatorAgent()
        agent3 = agents.ReplicatorAgent()

        self.add(agent1)
        self.add(agent2)
        self.add(agent3)
        self.db.commit()

        agent1.connect_to(agent2)
        agent1.connect_to(agent3)
        info = models.Info(origin=agent1, contents="foo")
        self.add(agent1, agent2, agent3, info)
        self.db.commit()

        agent1.transmit(what=models.Info, to_whom=agents.Agent)
        self.db.commit()

        agent2.receive_all()
        agent3.receive_all()
        self.db.commit()

        assert agent1.infos()[0].contents == agent2.infos()[0].contents
        assert agent1.infos()[0].contents == agent3.infos()[0].contents
        assert agent1.infos()[0].uuid != agent2.infos()[0].uuid != agent3.infos()[0].uuid

        transmissions = info.transmissions
        assert len(transmissions) == 2

    def test_transmit_selector_default(self):

        # Create a network of two biological agents.
        agent1 = agents.ReplicatorAgent()
        agent2 = agents.ReplicatorAgent()

        self.add(agent1)
        self.add(agent2)
        self.db.commit()

        agent1.connect_to(agent2)

        self.add(agent1)
        self.add(agent2)
        self.db.commit()

        meme = information.Meme(origin=agent1, contents="foo")
        gene = information.Gene(origin=agent1, contents="bar")
        self.add(meme)
        self.add(gene)
        self.db.commit()

        assert len(agent1.infos(type=Gene)) == 1
        assert len(agent1.infos(type=Gene)) == 1
        assert len(agent2.infos(type=Gene)) == 0
        assert len(agent2.infos(type=Gene)) == 0

        # Transmit from agent 1 to 2.
        agent1.transmit(to_whom=agent2)

        # Receive the transmission.
        agent2.receive_all()
        self.db.commit()

        # Make sure that Agent 2 has a blank memome and the right gene.
        assert "foo" == agent2.infos(type=Meme)[0].contents
        assert "bar" == agent2.infos(type=Gene)[0].contents

    def test_transmit_selector_specific_info(self):

        # Create a network of two biological agents.
        agent1 = agents.ReplicatorAgent()
        agent2 = agents.ReplicatorAgent()

        self.add(agent1)
        self.add(agent2)
        self.db.commit()

        agent1.connect_to(agent2)

        self.add(agent1)
        self.add(agent2)
        self.db.commit()

        meme = information.Meme(origin=agent1, contents="foo")
        gene = information.Gene(origin=agent1, contents="bar")
        self.add(meme)
        self.add(gene)
        self.db.commit()

        assert len(agent1.infos(type=Gene)) == 1
        assert len(agent1.infos(type=Gene)) == 1
        assert len(agent2.infos(type=Gene)) == 0
        assert len(agent2.infos(type=Gene)) == 0

        # Transmit from agent 1 to 2.
        agent1.transmit(what=gene, to_whom=agent2)

        # Receive the transmission.
        agent2.receive_all()
        self.db.commit()

        # Make sure that Agent 2 has a blank memome and the right gene.
        assert not agent2.infos(type=Meme)
        assert "bar" == agent2.infos(type=Gene)[0].contents

    def test_transmit_selector_all_of_type(self):

        # Create a network of two biological agents.
        agent1 = agents.ReplicatorAgent()
        agent2 = agents.ReplicatorAgent()

        self.add(agent1)
        self.add(agent2)
        self.db.commit()

        agent1.connect_to(agent2)

        self.add(agent1)
        self.add(agent2)
        self.db.commit()

        meme1 = information.Meme(origin=agent1, contents="foo1")
        meme2 = information.Meme(origin=agent1, contents="foo2")
        meme3 = information.Meme(origin=agent1, contents="foo3")
        gene = information.Gene(origin=agent1, contents="bar")
        self.add(meme1, meme2, meme3)
        self.add(gene)
        self.db.commit()

        assert len(agent1.infos(type=Meme)) == 3
        assert len(agent2.infos(type=Meme)) == 0
        assert len(agent1.infos(type=Gene)) == 1
        assert len(agent2.infos(type=Gene)) == 0

        # Transmit memes from agent 1 to 2.
        agent1.transmit(what=information.Meme, to_whom=agent2)

        # Receive the transmission.
        agent2.receive_all()
        self.db.commit()

        # Make sure that Agent 2 has a blank memome and the right gene.
        assert not agent2.infos(type=Gene)
        assert len(agent2.infos(type=Meme)) == 3
