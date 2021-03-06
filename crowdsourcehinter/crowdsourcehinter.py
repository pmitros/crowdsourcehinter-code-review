import ast
import logging
import operator
import pkg_resources
import random
import json
import copy

from xblock.core import XBlock
from xblock.fields import Scope, Dict, List, Boolean, String
from xblock.fragment import Fragment

log = logging.getLogger(__name__)

class CrowdsourceHinter(XBlock):
    """
    This is the Crowd Sourced Hinter XBlock. This Xblock seeks to provide students with hints
    that specifically address their mistake. Additionally, the hints that this Xblock shows
    are created by the students themselves. This doc string will probably be edited later.
    """
    # Database of hints. hints are stored as such: {"incorrect_answer": {"hint": rating}}. each key (incorrect answer)
    # has a corresponding dictionary (in which hints are keys and the hints' ratings are the values).
    #
    # Example: {"computerr": {"You misspelled computer, remove the last r.": 5}}
    hint_database = Dict(default={}, scope=Scope.user_state_summary)
    # Database of initial hints, set by the course instructor. If initial hints are set by the instructor, hint_database's contents
    # will become identical to initial_hints. The datastructure for initial_hints is the same as for hint_databsae,
    # {"incorrect_answer": {"hint": rating}}
    initial_hints = Dict(default={}, scope=Scope.content)
    # This is a list of incorrect answer submissions made by the student. this list is mostly used for
    # feedback, to find which incorrect answer's hint a student voted on.
    #
    # Example: ["personal computer", "PC", "computerr"]
    WrongAnswers = List([], scope=Scope.user_state)
    # A dictionary of generic_hints. default hints will be shown to students when there are no matches with the
    # student's incorrect answer within the hint_database dictionary (i.e. no students have made hints for the
    # particular incorrect answer)
    #
    # Example: ["Make sure to check your answer for simple mistakes, like spelling or spaces!"]
    generic_hints = List(default=[], scope=Scope.content)
    # List of which hints have been shown to the student
    # this list is used to prevent the same hint from showing up to a student (if they submit the same incorrect answers
    # multiple times)
    #
    # Example: ["You misspelled computer, remove the last r."]
    Used = List([], scope=Scope.user_state)
    # This list is used to prevent students from voting multiple times on the same hint during the feedback stage.
    # i believe this will also prevent students from voting again on a particular hint if they were to return to
    # a particular problem later
    Voted = List(default=[], scope=Scope.user_state)
    # This is a dictionary of hints that have been reported. the values represent the incorrect answer submission, and the
    # keys are the hints the corresponding hints. hints with identical text for differing answers will all not show up for the
    # student.
    #
    # Example: {"desk": "You're completely wrong, the answer is supposed to be computer."}
    Reported = Dict(default={}, scope=Scope.user_state_summary)
    # This string determines whether or not to show only the best (highest rated) hint to a student
    # When set to 'True' only the best hint will be shown to the student.
    # Details on operation when set to 'False' are to be finalized.
    show_best = Boolean(default=True, scope=Scope.user_state_summary)
    # This String represents the xblock element for which the hinter is running. It is necessary to manually
    # set this value in the XML file under the format "hinting_element": "i4x://edX/DemoX/problem/Text_Input" .
    # Setting the element in the XML file is critical for the hinter to work.
    Element = String(default="", scope=Scope.content)

    def studio_view(self, context=None):
        """
        This function defines a view for editing the XBlock when embedding it in a course. It will allow
        one to define, for example, which problem the hinter is for. It is unfinished and does not currently
        work.
        """
        html = self.resource_string("static/html/crowdsourcehinterstudio.html")
        frag = Fragment(html.format(self=self))
        frag.add_javascript_url('//cdnjs.cloudflare.com/ajax/libs/mustache.js/0.8.1/mustache.min.js')
        frag.add_css(self.resource_string("static/css/crowdsourcehinter.css"))
        frag.add_javascript(self.resource_string("static/js/src/crowdsourcehinter.js"))
        frag.initialize_js('CrowdsourceHinter')
        return frag

    def resource_string(self, path):
        """
        This function is used to get the path of static resources.
        """
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    def get_user_is_staff(self):
        """
        Return self.xmodule_runtime.user_is_staff
        This is not a supported part of the XBlocks API. User data is still
        being defined. However, It's the only way to get the data right now.
        """
        return self.xmodule_runtime.user_is_staff

    def student_view(self, context=None):
        """
        This view renders the hint view to the students. The HTML has the hints templated
        in, and most of the remaining functionality is in the JavaScript.
        """
        html = self.resource_string("static/html/crowdsourcehinter.html")
        frag = Fragment(html)
        frag.add_javascript_url('//cdnjs.cloudflare.com/ajax/libs/mustache.js/0.8.1/mustache.min.js')
        frag.add_css(self.resource_string("static/css/crowdsourcehinter.css"))
        frag.add_javascript(self.resource_string("static/js/src/crowdsourcehinter.js"))
        frag.initialize_js('CrowdsourceHinter', {'hinting_element': self.Element, 'isStaff': self.xmodule_runtime.user_is_staff})
        return frag

    @XBlock.json_handler
    def get_hint(self, data, suffix=''):
        """
        Returns hints to students. Hints with the highest rating are shown to students unless the student has already
        submitted the same incorrect answer previously.

        Args:
          data['submittedanswer']: The string of text that the student submits for a problem.

        returns:
          'Hints': the highest rated hint for an incorrect answer
                        or another random hint for an incorrect answer
                        or 'Sorry, there are no more hints for this answer.' if no more hints exist
        """
        # populate hint_database with hints from initial_hints if there are no hints in hint_database.
        # this probably will occur only on the very first run of a unit containing this block.
        if not bool(self.hint_database):
            self.hint_database = copy.copy(self.initial_hints)
        answer = str(data["submittedanswer"])
        answer = answer.lower() # for analyzing the student input string I make it lower case.
        found_equal_sign = 0
        remaining_hints = int(0)
        best_hint = ""
        # the string returned by the event problem_graded is very messy and is different
        # for each problem, but after all of the numbers/letters there is an equal sign, after which the
        # student's input is shown. I use the function below to remove everything before the first equal
        # sign and only take the student's actual input. This is not very clean.
        if "=" in answer:
            if found_equal_sign == 0:
                found_equal_sign = 1
                eqplace = answer.index("=") + 1
                answer = answer[eqplace:]
        remaining_hints = str(self.find_hints(answer))
        if remaining_hints != str(0):
            best_hint = max(self.hint_database[str(answer)].iteritems(), key=operator.itemgetter(1))[0]
            if self.show_best:
                # if set to show best, only the best hint will be shown. Different hints will not be shown
                # for multiple submissions/hint requests
                # currently set by default to True
                if best_hint not in self.Reported.keys():
                    self.Used.append(best_hint)
                    return {'Hints': best_hint, "StudentAnswer": answer}
            if best_hint not in self.Used:
                # choose highest rated hint for the incorrect answer
                if best_hint not in self.Reported.keys():
                    self.Used.append(best_hint)
                    return {'Hints': best_hint, "StudentAnswer": answer}
            # choose another random hint for the answer.
            temporary_hints_list = []
            for hint_keys in self.hint_database[str(answer)]:
                if hint_keys not in self.Used:
                    if hint_keys not in self.Reported:
                        temporary_hints_list.append(str(hint_keys))
                        not_used = random.choice(temporary_hints_list)
                        self.Used.append(not_used)
                        return {'Hints': not_used, "StudentAnswer": answer}
        # find generic hints for the student if no specific hints exist
        if len(self.generic_hints) != 0:
            not_used = random.choice(self.generic_hints)
            self.Used.append(not_used)
            return {'Hints': not_used, "StudentAnswer": answer}
        else:
            # if there are no more hints left in either the database or defaults
            self.Used.append(str("There are no hints for" + " " + answer))
            return {'Hints': "Sorry, there are no hints for this answer.", "StudentAnswer": answer}

    def find_hints(self, answer):
        """
        This function is used to find all appropriate hints that would be provided for
        an incorrect answer.

        Args:
          answer: This is equal to answer from get_hint, the answer the student submitted

        Returns 0 if no hints to show exist
        """
        isreported = []
        isused = 0
        self.WrongAnswers.append(str(answer)) # add the student's input to the temporary list
        if str(answer) not in self.hint_database:
            # add incorrect answer to hint_database if no precedent exists
            self.hint_database[str(answer)] = {}
            return str(0)
        for hint_keys in self.hint_database[str(answer)]:
            for reported_keys in self.Reported:
                if hint_keys == reported_keys:
                    isreported.append(hint_keys)
            if str(hint_keys) in self.Used:
                if self.show_best is False:
                    isused += 1
        if (len(self.hint_database[str(answer)]) - len(isreported) - isused) > 0:
            return str(1)
        else:
            return str(0)

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
        # feedback_data is a dictionary of hints (or lack thereof) used for a
        # specific answer, as well as 2 other random hints that exist for each answer
        # that were not used. The keys are the used hints, the values are the
        # corresponding incorrect answer
        feedback_data = {}
        if self.get_user_is_staff():
            if len(self.Reported) != 0:
                for answer_keys in self.hint_database:
                    if str(len(self.hint_database[str(answer_keys)])) != str(0):
                        for hints in self.hint_database[str(answer_keys)]:
                            for reported_hints in self.Reported:
                                if str(hints) == reported_hints:
                                    feedback_data[str(hints)] = str("Reported")
        if len(self.WrongAnswers) == 0:
            return feedback_data
        else:
            for index in range(0, len(self.Used)):
                # each index is a hint that was used, in order of usage
                if str(self.Used[index]) in self.hint_database[self.WrongAnswers[index]]:
                    # add new key (hint) to feedback_data with a value (incorrect answer)
                    feedback_data[str(self.Used[index])] = str(self.WrongAnswers[index])
                    self.WrongAnswers = []
                    self.Used = []
                    return feedback_data
                else:
                    # if the student's answer had no hints (or all the hints were reported and unavailable) return None
                    feedback_data[None] = str(self.WrongAnswers[index])
                    self.WrongAnswers = []
                    self.Used = []
                    return feedback_data
        self.WrongAnswers=[]
        self.Used=[]
        return feedback_data

    @XBlock.json_handler
    def get_ratings(self, data, suffix=''):
        """
        This function is used to return the ratings of hints during hint feedback.

        data['student_answer'] is the answer for the hint being displayed
        data['hint'] is the hint being shown to the student

        returns:
            hint_rating: the rating of the hint as well as data on what the hint in question is
        """
        hint_rating = {}
        if data['student_answer'] == 'Reported':
            hint_rating['rating'] = 0
            hint_rating['student_ansxwer'] = 'Reported'
            hint_rating['hint'] = data['hint']
            return hint_rating
        hint_rating['rating'] = self.hint_database[data['student_answer']][data['hint']]
        hint_rating['student_answer'] = data['student_answer']
        hint_rating['hint'] = data['hint']
        return hint_rating

    @XBlock.json_handler
    def rate_hint(self, data, suffix=''):
        """
        Used to facilitate hint rating by students.

        Hint ratings in hint_database are updated and the resulting hint rating (or reported status) is returned to JS.

        Args:
          data['student_answer']: The incorrect answer that corresponds to the hint that is being voted on
          data['hint']: The hint that is being voted on
          data['student_rating']: The rating chosen by the student.

        Returns:
          "rating": The rating of the hint.
        """
        answer_data = data['student_answer']
        data_rating = data['student_rating']
        data_hint = data['hint']
        if data['student_rating'] == 'unreport':
            for reported_hints in self.Reported:
                if reported_hints == data_hint:
                    self.Reported.pop(data_hint, None)
                    return {'rating': 'unreported'}
        if data['student_rating'] == 'remove':
            for reported_hints in self.Reported:
                if data_hint == reported_hints:
                    self.hint_database[self.Reported[data_hint]].pop(data_hint, None)
                    self.Reported.pop(data_hint, None)
                    return {'rating': 'removed'}
        if data['student_rating'] == 'report':
            # add hint to Reported dictionary
            self.Reported[str(data_hint)] = answer_data
            return {"rating": 'reported', 'hint': data_hint}
        if str(data_hint) not in self.Voted:
            self.Voted.append(str(data_hint)) # add data to Voted to prevent multiple votes
            rating = self.change_rating(data_hint, data_rating, answer_data) # change hint rating
            if str(rating) == str(0):
                return {"rating": str(0), 'hint': data_hint}
            else:
                return {"rating": str(rating), 'hint': data_hint}
        else:
            return {"rating": str('voted'), 'hint': data_hint}

    def change_rating(self, data_hint, data_rating, answer_data):
        """
        This function is used to change the rating of a hint when students vote on its helpfulness.
        Initiated by rate_hint. The temporary_dictionary is manipulated to be used
        in self.rate_hint

        Args:
          data_hint: This is equal to the data['hint'] in self.rate_hint
          data_rating: This is equal to the data['student_rating'] in self.rate_hint
          answer_data: This is equal to the data['student_answer'] in self.rate_hint

        Returns:
          The rating associated with the hint is returned. This rating is identical
          to what would be found under self.hint_database[answer_string[hint_string]]
        """
        if data_rating == 'upvote':
            self.hint_database[str(answer_data)][str(data_hint)] += 1
        else:
            self.hint_database[str(answer_data)][str(data_hint)] -= 1

    @XBlock.json_handler
    def add_new_hint(self, data, suffix=''):
        """
        This function adds a new hint submitted by the student into the hint_database.

        Args:
          data['submission']: This is the text of the new hint that the student has submitted.
          data['answer']: This is the incorrect answer for which the student is submitting a new hint.
        """
        submission = data['submission']
        answer = data['answer']
        if str(submission) not in self.hint_database[str(answer)]:
            self.hint_database[str(answer)].update({submission: 0})
            return
        else:
            # if the hint exists already, simply upvote the previously entered hint
            if str(submission) in self.generic_hints:
                return
            else:
                self.hint_database[str(answer)][str(submission)] += 1
                return

    @XBlock.json_handler
    def studiodata(self, data, suffix=''):
        """
        This function serves to return the dictionary of reported hints to JS. This is intended for use in
        the studio_view, which is under construction at the moment
        """
        return self.Reported

    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("CrowdsourceHinter",
            """
                <verticaldemo>
                    <crowdsourcehinter>
                        {"generic_hints": "Make sure to check for basic mistakes like typos", "initial_hints": {"michiganp": {"remove the p at the end", 0}, "michigann": {"too many Ns on there": 0}}, "hinting_element": "i4x://edX/DemoX/problem/Text_Input"}
                    </crowdsourcehinter>
                 </verticaldemo>
            """
            ),
        ]

    @classmethod
    def parse_xml(cls, node, runtime, keys, _id_generator):
        """
        A minimal working test for parse_xml
        """
        block = runtime.construct_xblock_from_class(cls, keys)
        xmlText = ast.literal_eval(str(node.text))
        block.generic_hints.append(str(xmlText["generic_hints"]))
        block.initial_hints = copy.copy(xmlText["initial_hints"])
        block.Element = str(xmlText["hinting_element"])
        return block
