# pylint: disable=line-too-long
# pylint: disable=unused-argument
import pkg_resources
import logging
import operator
import random
import ast

from xblock.core import XBlock
from xblock.fields import Scope, Dict, List
from xblock.fragment import Fragment

log = logging.getLogger(__name__)

class CrowdXBlock(XBlock):
    """
    This is the Crowd Sourced Hinter XBlock. This Xblock seeks to provide students with hints
    that specifically address their mistake. Additionally, the hints that this Xblock shows
    are created by the students themselves. This doc string will probably be edited later.
    """
    hint_database = Dict(default={"guess": {"hint": 1}}, scope=Scope.user_state_summary)
    # database of hints. hints are stored as such: {"incorrect_answer": {"hint": rating}}. each key (incorrect answer)
    # has a corresponding dictionary (in which hints are keys and the hints' ratings are the values).
    HintsToUse = Dict({}, scope=Scope.user_state)
    # this is a dictionary of hints that will be used to determine what hints to show a student.
    # flagged hints are not included in this dictionary of hints
    WrongAnswers = List([], scope=Scope.user_state)
    # this is a list of incorrect answer submissions made by the student. this list is mostly used for
    # feedback, to find which incorrect answer's hint a student voted on.
    DefaultHints = Dict(default={"default hint 1": 2, "default hint 2": 1, "default hint 3": 1}, scope=Scope.content)
    # a dictionary of default hints. default hints will be shown to students when there are no matches with the
    # student's incorrect answer within the hint_database dictionary (i.e. no students have made hints for the
    # particular incorrect answer)
    Used = List([], scope=Scope.user_state)
    # list of which hints from the HintsToUse dictionary have been shown to the student
    # this list is used to prevent the same hint from showing up to a student (if they submit the same incorrect answers
    # multiple times)
    Voted = List(default=[], scope=Scope.user_state)
    # this list is used to prevent students from voting multiple times on the same hint during the feedback stage.
    # i believe this will also prevent students from voting again on a particular hint if they were to return to
    # a particular problem later
    Flagged = Dict(default={"bad_hint": 1, "other_bad_hint": 4, "another_bad_hint": 3}, scope=Scope.user_state_summary)
    # this is a dictionary of hints that have been flagged. the keys represent the incorrect answer submission, and the
    # values are the hints the corresponding hints. even if a hint is flagged, if the hint shows up for a different
    # incorrect answer, i believe that the hint will still be able to show for a student

    def student_view(self, context=None):
        """
        Student_view docstring. May be edited later. This is a placeholder for now.
        """
        html = self.resource_string("static/html/crowdxblock.html")
        frag = Fragment(html.format(self=self))
        frag.add_css(self.resource_string("static/css/crowdxblock.css"))
        frag.add_javascript(self.resource_string("static/js/src/crowdxblock.js"))
        frag.initialize_js('CrowdXBlock')
        return frag

    def studio_view(self, context=None):
        """
        Studio_view docstring. This is also a place holder.
        """
        html = self.resource_string("static/html/crowdxblockstudio.html")
        frag = Fragment(html.format(self=self))
        frag.add_css(self.resource_string("static/css/crowdxblock.css"))
        frag.add_javascript(self.resource_string("static/js/src/crowdxblock.js"))
        frag.initialize_js('CrowdXBlock')
        return frag

    def resource_string(self, path):
        """
        This is also a place holder docstring.
        """
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    @XBlock.json_handler
    def clear_temp(self, data, suffix=''):
        """
        this clears all temprorary lists/dictionaries. This may not be relevant any longer
        but is intended to prevent hints from messing up when changing between units within
        a section
        """
        remove_list = []
        for used_hints in self.Used:
            remove_list.append(used_hints)
        for items in remove_list:
            self.Used.remove(items)
        remove_list = []
        for wrong_answers in self.WrongAnswers:
            remove_list.append(wrong_answers)
        for items in remove_list:
            self.WrongAnswers.remove(items)
        self.HintsToUse.clear()

    @XBlock.json_handler
    def get_hint(self, data, suffix=''):
        """
        Returns hints to students. Hints are placed into the HintsToUse dictionary if it is found that they
        are not flagged. Hints with the highest rating are shown to students unless the student has already
        submitted the same incorrect answer previously.

        Args:
          data['submittedanswer']: The string of text that the student submits for a problem.

        returns:
          'HintsToUse': the highest rated hint for an incorrect answer
                        or another random hint for an incorrect answer
                        or 'Sorry, there are no more hints for this answer.' if no more hints exist
        """
        answer = str(data["submittedanswer"])
        answer = answer.lower()
        foundeq = 0
        hints_used = 0
        if "=" in answer:
            if foundeq == 0:
                foundeq = 1
                eqplace = answer.index("=") + 1
                answer = answer[eqplace:]
        self.find_hints(answer)
        if str(answer) not in self.hint_database:
            self.hint_database[str(answer)] = {}
            self.HintsToUse.clear()
            self.HintsToUse.update(self.DefaultHints)
        if max(self.HintsToUse.iteritems(), key=operator.itemgetter(1))[0] not in self.Used:
            if max(self.HintsToUse.iteritems(), key=operator.itemgetter(1))[0] not in self.Flagged.keys():
                self.Used.append(max(self.HintsToUse.iteritems(), key=operator.itemgetter(1))[0])
                return {'HintsToUse': max(self.HintsToUse.iteritems(), key=operator.itemgetter(1))[0]}
        else:
            not_used = random.choice(self.HintsToUse.keys())
            for used_hints in self.Used:
                if used_hints in self.HintsToUse.keys():
                    hints_used += 1
            if str(len(self.HintsToUse)) > str(hints_used):
                while not_used in self.Used:
                    while not_used in self.Flagged.keys():
                        not_used = random.choice(self.HintsToUse.keys())
            else:
                self.Used.append(str("There are no hints for" + " " + answer))
                return {'HintsToUse': "Sorry, there are no more hints for this answer."}
            self.Used.append(not_used)
            return {'HintsToUse': not_used}

    def find_hints(self, answer):
        """
        This function is used to find all appropriate hints that would be provided for
        an incorrect answer. Flagged hints are not added into the HintsToUse dictionary.

        Args:
          answer: This is equal to answer from get_hint, the answer the student submitted
        """
        hints_exist = 0
        isflagged = []
        self.WrongAnswers.append(str(answer))
        for answer_keys in self.hint_database:
            temphints = str(self.hint_database[str(answer_keys)])
            if str(answer_keys) == str(answer):
                self.HintsToUse.clear()
                self.HintsToUse.update(ast.literal_eval(temphints))
        for hint_keys in self.HintsToUse:
            for flagged_keys in self.Flagged:
                if str(hint_keys) == str(flagged_keys):
                    isflagged.append(hint_keys)
        for flagged_keys in isflagged:
            del self.HintsToUse[flagged_keys]
        for answer_keys in self.HintsToUse:
            if answer_keys not in self.Used:
                hints_exist = 1
        if hints_exist == 0:
            self.HintsToUse.update(self.DefaultHints)

    @XBlock.json_handler
    def get_feedback(self, data, suffix=''):
        """
        This function is used to facilitate student feedback to hints. Specifically this function
        is used to send necessary data to JS about incorrect answer submissions and hints.

        Returns:
          feedback_data: This dicitonary contains all incorrect answers that a student submitted
                         for the question, all the hints the student recieved, as well as two
                         more random hints that exist for an incorrect answer in the hint_database
        """
        feedback_data = {}
        feedbacklist = []
        number_of_hints = 0
        if len(self.WrongAnswers) == 0:
            return
        else:
            for index in range(0, len(self.Used)):
                for answer_keys in self.hint_database:
                    if str(self.Used[index]) in self.hint_database[str(answer_keys)]:
                        feedback_data[str(self.Used[index])] = str(self.WrongAnswers[index])
                feedbacklist.append(str(self.Used[index]))
                for answer_keys in self.hint_database:
                    if str(answer_keys) == str(self.WrongAnswers[index]):
                        if str(len(self.hint_database[str(answer_keys)])) != str(0):
                            number_of_hints = 0
                            hint_key_shuffled = self.hint_database[str(answer_keys)].keys()
                            random.shuffle(hint_key_shuffled)
                            for random_hint_key in hint_key_shuffled:
                                if str(random_hint_key) not in self.Flagged.keys():
                                    if number_of_hints < 3:
                                        number_of_hints += 1
                                        feedback_data[str(random_hint_key)] = str(self.WrongAnswers[index])
                                        self.WrongAnswers.append(str(self.WrongAnswers[index]))
                                        self.Used.append(str(random_hint_key))
                        else:
                            self.no_hints(index)
                            feedback_data[str("There are no hints for" + " " + str(self.WrongAnswers[index]))] = str(self.WrongAnswers[index])
        return feedback_data

    def no_hints(self, index):
        """
        This function is used when no hints exist for an answer. The feedback_data within
        get_feedback is set to "there are no hints for" + " " + str(self.WrongAnswers[index])
        """
        self.WrongAnswers.append(str(self.WrongAnswers[index]))
        self.Used.append(str("There are no hints for" + " " + str(self.WrongAnswers[index])))

    @XBlock.json_handler
    def rate_hint(self, data, suffix=''):
        """
        Used to facilitate hint rating by students. Ratings are -1, 1, or 0. -1 is downvote, 1 is upvote, and 0 is
        when a student flags a hint. 'zzeerroo' is returned to JS when a hint's rating is 0 because whenever 0 was
        simply returned, JS would interpret it as null.

        Hint ratings in hint_database are updated and the resulting hint rating (or flagged status) is returned to JS.

        Args:
          data['answer']: The incorrect answer that corresponds to the hint that is being voted on
          data['value']: The hint that is being voted on
          data['student_rating']: The rating chosen by the student. The value is -1, 1, or 0.

        Returns:
          "rating": The rating of the hint. 'zzeerroo' is returned if the hint's rating is 0.
                    If the hint has already been voted on, 'You have already voted on this hint!'
                    will be returned to JS.
        """
        original_data = data['answer']
        answer_data = data['answer']
        data_rating = data['student_rating']
        data_value = data['value']
        answer_data = self.remove_symbols(answer_data)
        if str(data['student_rating']) == str(0):
            self.hint_flagged(data['value'], answer_data)
            return {"rating": 'thiswasflagged', 'origdata': original_data}
        if str(answer_data) not in self.Voted:
            self.Voted.append(str(answer_data))
            rating = self.change_rating(data_value, int(data_rating), answer_data)
            print str(self.change_rating(data['value'], int(data['student_rating']), answer_data))
            if str(rating) == str(0):
                return {"rating": str('zzeerroo'), 'origdata': original_data}
            else:
                return {"rating": str(rating), 'origdata': original_data}
        else:
            return {"rating": str('You have already voted on this hint!'), 'origdata': original_data}

    def hint_flagged(self, data_value, answer_data):
        """
        This is used to add a hint to the self.flagged dictionary. When a hint is returned with the rating
        of 0, it is considered to be flagged.

        Args:
          data_value: This is equal to the data['value'] in self.rate_hint
          answer_data: This is equal to the data['answer'] in self.rate_hint
        """
        for answer_keys in self.hint_database:
            if answer_keys == data_value:
                for hint_keys in self.hint_database[str(answer_keys)]:
                    if str(hint_keys) == answer_data:
                        self.Flagged[str(hint_keys)] = str(answer_keys)

    def change_rating(self, data_value, data_rating, answer_data):
        """
        This function is used to change the rating of a hint when it is voted on.
        Initiated by rate_hint. The temporary_dictionary is manipulated to be used
        in self.rate_hint

        Args:
          data_value: This is equal to the data['value'] in self.rate_hint
          data_rating: This is equal to the data['student_rating'] in self.rate_hint
          answer_data: This is equal to the data['answer'] in self.rate_hint

        Returns:
          The rating associated with the hint is returned. This rating is identical
          to what would be found under self.hint_database[answer_string[hint_string]]
        """
        for hint_keys in self.Used:
            if str(hint_keys) == str(answer_data):
                answer = self.Used.index(str(answer_data))
                for answer_keys in self.hint_database:
                    temporary_dictionary = str(self.hint_database[str(answer_keys)])
                    temporary_dictionary = (ast.literal_eval(temporary_dictionary))
                    if str(answer_keys) == str(self.WrongAnswers[answer]):
                        temporary_dictionary[self.Used[int(answer)]] += int(data_rating)
                        self.hint_database[str(answer_keys)] = temporary_dictionary
                        return str(temporary_dictionary[self.Used[int(answer)]])

    def remove_symbols(self, answer_data):
        """
        For removing colons and such from answers to prevent weird things from happening. Not sure if this is properly functional.

        Args:
          answer_data: This is equal to the data['answer'] in self.rate_hint

        Returns:
          answer_data: This is equal to the argument answer_data except that symbols have been
                       replaced by text (hopefully)
        """
        answer_data = answer_data.replace('ddeecciimmaallppooiinntt', '.')
        answer_data = answer_data.replace('qquueessttiioonnmmaarrkk', '?')
        answer_data = answer_data.replace('ccoolloonn', ':')
        answer_data = answer_data.replace('sseemmiiccoolloonn', ';')
        answer_data = answer_data.replace('eeqquuaallss', '=')
        answer_data = answer_data.replace('qquuoottaattiioonnmmaarrkkss', '"')
        return answer_data

    @XBlock.json_handler
    def moderate_hint(self, data, suffix=''):
        """
        under construction, intended to be used for instructors to remove hints from the database after hints
        have been flagged.
        """
        flagged_hints = {}
        flagged_hints = self.Flagged
        if data['rating'] == "dismiss":
            flagged_hints.pop(data['answer_wrong'], None)
        else:
            flagged_hints.pop(data['answer_wrong'], None)
            for answer_keys in self.hint_database:
                if str(answer_keys) == data['answ']:
                    for hint_keys in self.hint_database[str(answer_keys)]:
                        if str(hint_keys) == data['hint']:
                            temporary_dict = str(self.hint_database[str(answer_keys)])
                            temporary_dict = (ast.literal_eval(temporary_dict))
                            temporary_dict.pop(hint_keys, None)
                            self.hint_database[str(answer_keys)] = temporary_dict

    @XBlock.json_handler
    def give_hint(self, data, suffix=''):
        """
        This function adds a new hint submitted by the student into the hint_database.

        Args:
          data['submission']: This is the text of the new hint that the student has submitted.
          data['answer']: This is the incorrect answer for which the student is submitting a new hint.
        """
        submission = data['submission'].replace('ddeecciimmaallppooiinntt', '.')
        hint_id = data['answer'].replace('ddeecciimmaallppooiinntt', '.')
        for answer_keys in self.hint_database:
            if str(answer_keys) == self.WrongAnswers[self.Used.index(hint_id)]:
                if str(submission) not in self.hint_database[str(answer_keys)]:
                    temporary_dictionary = str(self.hint_database[str(answer_keys)])
                    temporary_dictionary = (ast.literal_eval(temporary_dictionary))
                    temporary_dictionary.update({submission: 0})
                    self.hint_database[str(answer_keys)] = temporary_dictionary
                    return
                else:
                    hint_index = self.Used.index(submission)
                    for default_hints in self.DefaultHints:
                        if default_hints == self.Used[int(hint_index)]:
                            self.DefaultHints[str(default_hints)] += int(1)
                            return
                    for answer_keys in self.hint_database:
                        temporary_dictionary = str(self.hint_database[str(answer_keys)])
                        temporary_dictionary = (ast.literal_eval(temporary_dictionary))
                        if str(answer_keys) == str(self.WrongAnswers[int(hint_index)]):
                            temporary_dictionary[self.Used[int(hint_index)]] += int(data['rating'])
                            self.hint_database[str(answer_keys)] = temporary_dictionary

    @XBlock.json_handler
    def studiodata(self, data, suffix=''):
        """
        This function serves to return the dictionary of flagged hints to JS. This is intended for use in
        the studio_view, which is under construction at the moment
        """
        return self.Flagged

    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("CrowdXBlock",
             """<vertical_demo>
<crowdxblock/>
</vertical_demo>
"""),
        ]
